# YouTube Transcript Extractor

## Overview

A Flask-based web application designed for YouTube transcript extraction and analysis. This tool leverages OpenAI's API capabilities to transform video transcripts into actionable insights and summaries.

## Core Features

- **Transcript Extraction:** Process YouTube videos and playlists
- **AI-Powered Analysis:** Generate summaries using OpenAI
- **Progress Tracking:** Real-time monitoring of transcript processing
- **Batch Processing:** Handle multiple videos simultaneously
- **Video Metadata:** 
  - Video titles and IDs
  - Channel names
  - Publication dates in standardized UTC format
  - Graceful handling of missing metadata

## Tech Stack

### Backend
- **Python:** 3.8+
- **Web Framework:** Flask
- **APIs:**
  - YouTube Data API v3
  - OpenAI API
- **Libraries:**
  - `youtube-transcript-api`: For transcript extraction
  - `requests`: HTTP client for API calls
  - `python-dotenv`: Environment variable management
  - Other dependencies listed in `requirements.txt`

## Prerequisites

- Python 3.8 or higher
- YouTube Data API access (Get it from [Google Cloud Console](https://console.cloud.google.com/))
- OpenAI API key (Get it from [OpenAI Platform](https://platform.openai.com/api-keys))

## Quick Start

### 1. Environment Setup

```bash
# Clone repository
git clone https://github.com/yourusername/youtube-transcript-extractor.git
cd youtube-transcript-extractor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file with your credentials:

```env
FLASK_SECRET_KEY=your_secure_secret_key
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini-2024-07-18  # You can change this to any available OpenAI model
```

Note: Replace the placeholder values with your actual API keys:
- Get your YouTube API key from Google Cloud Console
- Get your OpenAI API key from OpenAI Platform
- Generate a secure random string for FLASK_SECRET_KEY
- OPENAI_MODEL can be changed to any available OpenAI model (e.g., gpt-3.5-turbo, gpt-4, etc.)

### Output Format

The application generates detailed transcripts with the following information:
- Video title and ID
- Channel name
- Publication date (in YYYY-MM-DD HH:MM:SS UTC format)
- AI-generated summary
- Key points and tags
- Full formatted transcript

Missing information (e.g., publication dates) is handled gracefully with "Not available" placeholders.

### 3. Running the Application

The application runs on port 5000 by default. Here are the ways to start it:

#### Option 1: Using Python directly
```bash
# Make sure your virtual environment is activated
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Run the application
python app.py
```

#### Option 2: Using Flask CLI
```bash
# Make sure your virtual environment is activated
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Export Flask environment variables
export FLASK_APP=app.py
export FLASK_DEBUG=1  # Enable debug mode (optional)

# Run Flask
flask run
```

The application will be available at `http://localhost:5000`

#### Troubleshooting Port Issues

- **MacOS Users:** Port 5000 might be used by AirPlay Receiver. If you see a "Port in use" error, you can:
  ```bash
  # Option 1: Use a different port
  flask run --port=5001
  # or with Python directly
  python app.py --port=5001
  ```
  Or disable AirPlay Receiver in System Preferences -> General -> AirDrop & Handoff

- **Other Operating Systems:** If port 5000 is already in use by another application, you can similarly specify a different port using the commands above.

## Usage

1. Access the web interface at `http://localhost:5000`
2. Input YouTube video URLs or playlist URLs
3. Monitor the progress of transcript extraction and processing
4. Download the processed results

### API Keys Security
- Never commit your `.env` file to version control
- Keep your API keys secure and rotate them periodically
- Monitor your API usage to avoid exceeding quotas

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
