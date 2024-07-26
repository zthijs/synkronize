# Synkronize

Synkronize is a NestJS-based API designed to synchronize music playback with smart lights and other devices. This application integrates with Spotify and Dirigera to create a seamless experience for controlling smart lights based on the music being played.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [License](#license)

## Features

- Synchronize music playback with smart lights.
- Integrate with Spotify for music playback data.
- Control smart lights using Dirigera.
- Comprehensive API documentation using Swagger.

## Requirements

- Node.js (v20 or higher)
- npm (v10 or higher)
- SQLite

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/zthijs/synkronize.git
   cd synkronize
   ```

2. Install the dependencies:

   ```bash
   npm install
   ```

## Configuration

Create a `.env` file in the root directory of the project and add the following environment variables:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=your_spotify_redirect_uri
DIRIGERA_ACCESS_TOKEN=your_dirigera_access_token
```

Replace `your_spotify_client_id`, `your_spotify_client_secret`, `your_spotify_redirect_uri`, and `your_dirigera_access_token` with your actual Spotify and Dirigera credentials.

### Obtaining Dirigera Access Token

To get a Dirigera access token, execute the following command:

```bash
npx dirigera authenticate
```

Follow the prompts to authenticate and obtain your access token.

## Running the Application

1. Run the database migrations (if any):

   ```bash
   npm run migration:run
   ```

2. Start the application:

   ```bash
   npm run start
   ```

3. The application will be running on `http://localhost:3000`.

## API Documentation

The API documentation is available at `http://localhost:3000/ui` once the application is running. This documentation is generated using Swagger and provides detailed information about the available endpoints and their usage.