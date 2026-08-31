FROM ghcr.io/prefix-dev/pixi:0.78.0 AS build

# copy source code, pixi.toml and pixi.lock to the container
WORKDIR /app
COPY . .
# install dependencies to `/app/.pixi/envs/default`
# use `--locked` to ensure the lockfile is up to date with pixi.toml
RUN pixi install --locked
# create the shell-hook bash script to activate the environment
RUN pixi shell-hook -s bash > /shell-hook
RUN echo "#!/bin/bash" > /app/entrypoint.sh
RUN cat /shell-hook >> /app/entrypoint.sh
# extend the shell-hook script to run the command passed to the container
RUN echo 'exec "$@"' >> /app/entrypoint.sh

FROM ubuntu:24.04 AS production
WORKDIR /app
# only copy the production environment into prod container
# please note that the "prefix" (path) needs to stay the same as in the build container
COPY --from=build /app/.pixi/envs /app/.pixi/envs
COPY --from=build --chmod=0775 /app/entrypoint.sh /app/entrypoint.sh

USER ubuntu

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "strucTFactor", "--help" ]
