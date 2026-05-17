![Chessmate logo](/app/static/images/Chessmate.png)

# About
Chessmate is a chess match and tournament tracking website. Its the perfect place to keep the records of all your chess matches and analyse them in one place.

# Features

### Users
* Add records of matches and tournaments
* View player's statistics.
* Connect with other users and compare statistics.
* View the leaderboard to compare rankings with other users in the website
* Use the calendar to view upcoming tournaments.
* Submit queries in regards to the website.
* Play a chess minigame to improve skills and knowledge
### Admins
* View queries sent by users
* Change status of queries
* Reply to users regarding their queries through email

# How to Run

1. Clone the repository:
   ```
   git clone https://github.com/Linsoyjoy/Agile-web-dev.git
   cd Agile-web-dev
   ```

2. Create and activate a virtual environment:
   ```
   python3 -m venv .venv
   source .venv/bin/activate        # Mac/Linux
   .venv\Scripts\activate           # Windows
   ```

3. Install dependencies:
   ```
   pip install -r project/requirements.txt
   ```

4. Create a `.env` file:
   Create a file named `.env` with the following content:
   ```
   SECRET_KEY=any-random-string-here
   ```

5. Create the database folder:
   ```
   mkdir -p database
   ```

6. Run the app:
   ```
   python3 run.py
   ```

7. Open `http://127.0.0.1:5000` in your browser.

8. Sign up for an account to get started. The database is created automatically on first run.

9. (optional) run `populate_database.py` to populate the site
    ```
   python3 populate_database.py
    ``` 

# Group Members

|Name|Student ID|GitHub Username|
|-|-|-|
|Alexei Samarin|24355378|student2414|
|Jessie Chen|24721859|whytothewhat|
|Lindsay Wijaya|24554944|Linsoyjoy|
|Sam Hunt|23951196|Jintexdemer|

Chessmate was made for the 2026 CITS3401 group project



