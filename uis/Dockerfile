FROM node:22-alpine

WORKDIR /workspace

# Preserve the npm workspace graph so the backoffice resolves the local
# business-logic package while each UI remains independently runnable.
COPY package.json package-lock.json ./
COPY packages/business-logic/package.json packages/business-logic/package.json
COPY packages/programming-fundamentals/package.json packages/programming-fundamentals/package.json
COPY packages/shared/package.json packages/shared/package.json
COPY uis/website/package.json uis/website/package.json
COPY uis/backoffice/package.json uis/backoffice/package.json
COPY uis/talent-pipeline-tracker/package.json uis/talent-pipeline-tracker/package.json
# Include the root's explicit optional native packages. npm lockfiles generated
# on macOS can otherwise omit the Linux musl binaries required by Alpine.
RUN npm ci --workspace=@trackflow/website --workspace=@trackflow/backoffice --workspace=@trackflow/business-logic --include-workspace-root=true

COPY packages/business-logic packages/business-logic
COPY docs/telemetry/event-schemas.json docs/telemetry/event-schemas.json
COPY uis/website uis/website
COPY uis/backoffice uis/backoffice
COPY uis/start.sh uis/start.sh

RUN chmod +x /workspace/uis/start.sh

EXPOSE 3000 3001

CMD ["/workspace/uis/start.sh"]
