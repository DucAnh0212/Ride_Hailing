FROM node:22-alpine

RUN apk add --no-cache bash

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

EXPOSE 3000
CMD ["npm", "start"]
