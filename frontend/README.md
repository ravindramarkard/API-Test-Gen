# API Test Generation Frontend

React + TypeScript frontend for the API Test Generation Platform.

## Setup

### Using npm

```bash
# Install dependencies
npm install

# Start development server
npm start
```

The app will be available at http://localhost:3000

### Using Docker

```bash
docker-compose up frontend
```

## Environment Variables

Create a `.env` file in the frontend directory:

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## Build for Production

```bash
npm run build
```

## Project Structure

```
frontend/
├── public/          # Static files
├── src/
│   ├── components/ # Reusable components
│   ├── pages/      # Page components
│   ├── services/   # API services
│   ├── store/      # Redux store and slices
│   └── hooks/      # Custom hooks
└── package.json
```

## Available Scripts

- `npm start` - Start development server
- `npm build` - Build for production
- `npm test` - Run tests
- `npm eject` - Eject from Create React App




