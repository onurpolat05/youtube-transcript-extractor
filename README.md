# YouTube Transcript Extractor

A Flask-based web application for extracting, processing, and downloading transcripts from YouTube playlists. Utilizes OpenAI's API for processing transcripts, providing summaries, tags, key points, and more.

## Features

- **Playlist Transcript Extraction:** Fetch transcripts from YouTube playlists.
- **OpenAI Integration:** Process transcripts using OpenAI's API to generate summaries, tags, key points, research implications, code snippets, technical concepts, market insights, and strategic implications.
- **Batch Processing:** Handle multiple transcripts simultaneously with rate limiting and retry mechanisms.
- **Progress Tracking:** 
  - Separate progress bars for each phase:
    - **Scraping Transcripts:** Track the number of videos scraped.
    - **Processing Transcripts:** Monitor the processing of transcripts via OpenAI.
    - **Merging Transcripts:** Track the merging of processed transcripts.
  - Elapsed time counters for each phase.
- **Download Processed Transcripts:** Users can download the processed transcripts as a text file.
- **UI Enhancements:** 
  - Intuitive interface with error handling, loading spinners, and detailed logs.
  - Responsive layout with collapsible log sections.
  - Enhanced buttons for initiating processing and downloading transcripts.

## Installation

1. **Clone the Repository**

    ```bash
    git clone https://github.com/yourusername/youtube-transcript-extractor.git
    cd youtube-transcript-extractor
    ```

2. **Create a Virtual Environment**

    ```bash
    python -m venv youtube_script
    source youtube_script/bin/activate  # On Windows: youtube_script\Scripts\activate
    ```

3. **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

4. **Configure Environment Variables**

    Create a `.env` file in the root directory and add:

    ```env
    FLASK_SECRET_KEY=your_flask_secret_key
    YOUTUBE_API_KEY=your_youtube_api_key
    OPENAI_API_KEY=your_openai_api_key
    ```

## Usage

1. **Run the Application**

    ```bash
    python app.py
    ```

2. **Access the Web Interface**

    Open your browser and navigate to `http://127.0.0.1:5000`.

3. **Process Transcripts**

    - Enter a YouTube playlist URL.
    - Select videos and click "Process Transcripts".
    - Monitor progress through separate progress bars for scraping, processing, and merging phases.
    - View elapsed time for each phase.
    - Once processing is complete, download the processed transcripts.

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the Repository**

2. **Create a New Branch**

    ```bash
    git checkout -b feature/YourFeatureName
    ```

3. **Commit Your Changes**

    ```bash
    git commit -m "Add your message here"
    ```

4. **Push to the Branch**

    ```bash
    git push origin feature/YourFeatureName
    ```

5. **Open a Pull Request**

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Flask](https://flask.palletsprojects.com/)
- [YouTube Transcript API](https://github.com/jdepoix/youtube-transcript-api)
- [OpenAI API](https://beta.openai.com/docs/)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)
- [Other Dependencies](requirements.txt)

## Troubleshooting

- **OpenAI API Key Issues:**
  - Ensure that the `OPENAI_API_KEY` is correctly set in the `.env` file.
  - Verify that the API key has the necessary permissions and is active.

- **Environment Setup:**
  - Make sure you're using the correct Python version as specified in `pyvenv.cfg`.
  - If you encounter issues with `python-dotenv`, ensure it's properly installed and imported.

- **Server Errors:**
  - Check the logs for detailed error messages.
  - Ensure all environment variables are correctly set.
  - Verify that the YouTube API key has sufficient quota and access.

## Future Improvements

- **Enhanced Error Handling:** Improve the application's resilience against API downtimes and invalid inputs.
- **User Authentication:** Implement user login to manage personal playlists and transcripts.
- **Support for More Formats:** Allow downloading transcripts in various formats like JSON, CSV, or PDF.
- **Performance Optimization:** Utilize more advanced concurrency techniques to speed up processing.
- **UI/UX Enhancements:** Further improve the user interface for better accessibility and user experience.
