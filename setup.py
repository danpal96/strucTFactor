from setuptools import setup

setup(
    name="strucTFactor",
    version="0.1.0",
    packages=["strucTFactor", "strucTFactor.deeptfactor"],
    package_data={
        "strucTFactor": ["strucTFactor_model.pt"],
    },
    entry_points={
        "console_scripts": [
            "strucTFactor=strucTFactor.predictTFwithStrucTFactor:main",
        ],
    },
)
