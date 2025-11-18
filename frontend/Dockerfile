# Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# Копируем package files
COPY package*.json ./

# Устанавливаем зависимости
RUN npm ci

# Копируем исходный код
COPY . .

# Переменные окружения для Vite
ENV VITE_API_URL=http://localhost:8000

EXPOSE 5173

# Запуск dev сервера (production: npm run build + nginx)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
