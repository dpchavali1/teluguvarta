# apps/web and apps/admin image. Build context = repo root.
#   docker build -f infra/deploy/next.Dockerfile --build-arg APP=web --build-arg PORT=3000 ...
# NEXT_PUBLIC_* are inlined at build time, so they are build args.
FROM node:22-slim
ARG APP
ARG PORT=3000
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WEB_URL
ARG NEXT_PUBLIC_SENTRY_DSN=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WEB_URL=$NEXT_PUBLIC_WEB_URL \
    NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN \
    NEXT_TELEMETRY_DISABLED=1 \
    APP=$APP PORT=$PORT
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/$APP apps/$APP
COPY packages packages
# apps/admin imports apps/web's design tokens by relative path.
COPY apps/web/src/app/tokens.css apps/web/src/app/tokens.css
RUN pnpm install --frozen-lockfile --filter "./apps/$APP..."
RUN pnpm --filter "./apps/$APP" build
ENV NODE_ENV=production
EXPOSE $PORT
CMD ["sh", "-c", "cd apps/$APP && exec node_modules/.bin/next start -p $PORT"]
