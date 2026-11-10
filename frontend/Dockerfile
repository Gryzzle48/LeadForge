FROM node:18-alpine

WORKDIR /app

# Baked into the Next.js rewrite at build time.
# Default matches an API running on the same machine.
# Docker Compose overrides this to http://backend:8000 so the site container
# can reach the API by its service name.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_API_KEY=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=10 \
  CMD node -e "require('http').get('http://127.0.0.1:3000',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
