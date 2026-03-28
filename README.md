<p align="center">
  <img src="other\banner.png" alt="MEOW Logo" width="100%">
</p>

# MEOW: Monitoring & Evaluation of Online Writing

> **Your personal detective in the world of disinformation.**
> Built with ❤️ during EUDIS Defence Hackathon.

[](https://opensource.org/licenses/MIT)

## Why MEOW? (Our Mission)

The internet is flooded with disinformation, and well-written fake news easily lowers our guard. Manual source-checking takes too much time, and the "red flags" are often invisible to the average user.

We believe that **truth and transparency shouldn't be hidden behind a paywall.** That's why we created MEOW as a 100% open-source, non-profit project. We want to empower everyday users to critically evaluate online content and help researchers study disinformation.

## Core Features

We don't just throw random numbers at the user. MEOW is built on transparency and analyzes websites across three/four main pillars (depends on the website type):

  * **Domain Trust:** Checks SSL security, domain age, and registration history.
  * **Language Trust:** Detects highly emotional tone, slang, or manipulative writing styles.
  * **Source Trust:** Identifies the presence (or suspicious absence) of owners, publication dates, and credible citations.
  * **Transparency:** Checks transparency of news articles etc. by analyzing the authors, date and text structure.

## How it Works (The Pipeline)

1.  **Scraping:** Extracts text and metadata directly from the active webpage.
2.  **Heuristics & AI Analysis:** Evaluates technical indicators and uses AI to identify the page type and language patterns.
3.  **Scoring Engine:** Calculates a weighted risk score based on the extracted metrics.
4.  **Real-time UI:** Generates instant signals and warnings in the browser extension.

## Installation (For Developers)

Since we are in active development, you can run the MEOW extension locally:

1.  **Clone this repository:**

    ```bash
    git clone https://github.com/[YOUR_USERNAME]/MEOW.git
    ```

2.  **Enter the backend folder:**

    ```bash
    cd backend
    ```

3.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    ```

    **Windows:**

    ```bash
    venv\Scripts\activate
    ```

    **Mac/Linux:**

    ```bash
    source venv/bin/activate
    ```

4.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

5.  **Get an API key** for gemma-3-4b-it.

6.  **Create the `.env` file** (in the backend folder).

    **.env Structure:**

    ```env
    GEMINI_API_KEY=[YOUR_API_KEY]
    GEMINI_MODEL=gemma-3-4b-it
    PORT=8000
    ```

7.  **Run the server:**

    ```bash
    python main.py
    ```

8.  **Install the extension** in your browser.

9.  **Congrats, you can now run the project :3**
