FROM node:22-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/chatgpt-academic-writing-toolkit/package*.json ./apps/chatgpt-academic-writing-toolkit/
RUN npm ci --prefix apps/chatgpt-academic-writing-toolkit --omit=dev

COPY scripts ./scripts
COPY apps/chatgpt-academic-writing-toolkit ./apps/chatgpt-academic-writing-toolkit

ENV HOST=0.0.0.0
ENV PORT=3000
ENV NODE_ENV=production

EXPOSE 3000

CMD ["npm", "--prefix", "apps/chatgpt-academic-writing-toolkit", "start"]
