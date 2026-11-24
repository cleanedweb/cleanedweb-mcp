# Builds the stdio proxy in packages/npm from the repository root, for directories
# such as Glama that build and inspect the server: docker build -t cleanedweb-mcp .
# Set CLEANEDWEB_API_KEY for the full catalog; without it the proxy uses the public
# profile (find_api and get_api).
FROM node:22-alpine AS build
WORKDIR /app
COPY packages/npm/package.json packages/npm/package-lock.json packages/npm/tsconfig.json packages/npm/tsconfig.build.json ./
RUN npm ci
COPY packages/npm/src ./src
RUN npm run build && npm prune --omit=dev

FROM node:22-alpine
WORKDIR /app
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
USER node
ENTRYPOINT ["node", "dist/cli.js"]
