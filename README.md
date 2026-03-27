# MASCAC Baseball Scouting Report Dashboard
## Project Overview
As a Division 3 college baseball player, scouting reports are hard to come by. 
Data is limited on other teams, and most of our game plan revolves around last season's results. 
I wanted to be able to organize the available data in the best way possible to help my team get a leg up on game day.
With this dashboard, my teammates will be able to view opposing players' stats and trends, as well as notes that can be added by users (my teammates).
I focused only on teams in the MASCAC, our conference, since a majority of our season is comprised of conference games, and they matter most for our playoff standing.
This project was made with the help of Claude code.

## Data Collection and Storage
The data I collected comes entirely from the MASCAC website (https://mascac.com/). I used the BeautifulSoup package to pull all the data from the website.
I used the tables from the stat leaders to get qualified player statistics for both pitchers and hitters. 
I also wanted to obtain game logs for individual players to show trends over time.
Each player has a profile on the website that shows a game log with all their stats. 
To load league data in, you need the URL and table ID to scrape it properly. 
The reason I don't just download CSV data is that I want this dashboard to update throughout the season as the website is updated.
To load in game logs, it is a similar process.
However, each URL is going to be different. So, you need to store the format to be called in your scraping method for when that individual player is called.
League data is loaded immediately, but player game logs aren't loaded in until they are called in the dashboard.
Each player's game log data is stored in a cache after being called so that you don't have to call the data every time you go back and forth from that player's profile.

There is also a section added for notes. This was added with the deployment of the dashboard, so it cannot be stored in the code. 
To keep this feature open for others to contribute, I used Supabase to store the data.

## Dashboard Layout/UI
