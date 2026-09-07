# given a pdb file as argument, this file predict, whether it is an transcription factor or not.
# you can choose your own pre-trained model or take the default model
# run it via: python predictTFwithStrucTFactor.py -i example.pdb -o output.csv -ckpt strucTFactor_model.pt -g cuda:0
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import torch
from Bio.PDB import DSSP, MMCIFParser, PDBParser
from importlib_resources import files
from torch.utils.data import DataLoader

from strucTFactor.deeptfactor.data_loader import EnzymeDataset_spatial
from strucTFactor.deeptfactor.models import DeepTFactor
from strucTFactor.deeptfactor.utils import argument_parser


def argument_parser():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--device",
        required=False,
        default="cpu",
        help="Specify device (Default: cpu)",
    )
    parser.add_argument(
        "-c",
        "--checkpoint",
        required=False,
        default=files("strucTFactor").joinpath("strucTFactor_model.pt"),
        help="Checkpoint file",
    )
    parser.add_argument("-i", "--input", required=True, nargs="+", help="Input files")
    parser.add_argument(
        "-f",
        "--format",
        choices=["pdb", "mmcif"],
        default="pdb",
        help="input format (Default: pdb)",
    )
    parser.add_argument("-o", "--output", required=True, help="Output file")
    parser.add_argument(
        "-t",
        "--threads",
        required=False,
        default=1,
        type=int,
        help="Number of threads (Default: 1)",
    )
    return parser


def get_spatial_string(path, seq_id, file_format="pdb"):
    if file_format == "pdb":
        parser = PDBParser()
    elif file_format == "mmcif":
        parser = MMCIFParser()
    else:
        raise ValueError(f"Invalid file_format: {file_format}")
    structure = parser.get_structure(seq_id, path)
    model = structure[0]
    dssp = DSSP(model, path, dssp="dssp")
    dssp_keys = list(dssp.keys())

    seq = []
    spatial_str = []
    for key in dssp_keys:
        if dssp[key][2] in ("B", "E"):
            spatial_str.append("b")
        elif dssp[key][2] in ("H", "G", "I"):
            spatial_str.append("a")
        else:
            spatial_str.append("N")
        seq.append(dssp[key][1])

    spatial_str = "".join(spatial_str)
    seq = "".join(seq)

    return [seq, spatial_str]


def main():
    parser = argument_parser()
    args = parser.parse_args()
    device = torch.device(args.device)
    checkpt_file = args.checkpoint
    input_files = args.input
    file_format = args.format
    output_path = args.output
    threads = args.threads
    # Load the model
    model = DeepTFactor(
        1,
        out_features=[1],
    )
    model = model.to(device)
    ckpt = torch.load(f"{checkpt_file}", map_location=device)
    model.load_state_dict(ckpt["model"])

    cutoff = 0.5

    # run DSSP to get spatial information
    future_dict = {}
    executor = ProcessPoolExecutor(max_workers=threads)
    for file in input_files:
        seq_id = Path(file).with_suffix("").name
        future = executor.submit(
            get_spatial_string, file, seq_id, file_format=file_format
        )
        future_dict[future] = seq_id

    with torch.no_grad(), open(output_path, "w") as out_file:
        model.eval()
        for future in as_completed(future_dict):
            seq_id = future_dict[future]
            try:
                protein_seqs, spatial_seqs = future.result()
            except Exception as exc:
                print(f"Error: {exc}")
                continue
            length = len(protein_seqs)
            if length > 1000:
                print(f"Warning: {seq_id} is too long ({length})")
                continue
            protein_seqs += "_" * (1000 - length)  # zero-padding
            proteinDataset = EnzymeDataset_spatial(
                [protein_seqs], torch.zeros([1, 1]), [spatial_seqs], 1
            )

            test_loader = DataLoader(proteinDataset, batch_size=1, shuffle=False)
            for x, _ in test_loader:
                x = x.type(torch.FloatTensor)
                output = model(x.to(device))
                prediction = output.cpu()
            if prediction.item() > cutoff:
                print(f"Prediction for {seq_id}: Transcription Factor")
            else:
                print(f"Prediction for {seq_id}: Not a Transcription Factor")
            out_file.write(f"{seq_id}\t{prediction.item()}\n")


if __name__ == "__main__":
    main()
