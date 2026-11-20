# Course notebooks: how to start

1. **Unzip** this package anywhere you like. It only holds a few files, so this takes seconds. Do not run anything from inside the zip.
2. **Start it**
   - **Windows:** double-click `Start.bat`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway**.
   - **Mac:** right-click `Start.command`, choose **Open**, then **Open** again. (Only the first time.)
3. A black window opens. **The very first time** it says "Setting up the course tools": this takes a minute or two, just wait. After
   that, your browser shows the list of notebooks. Click the one you need. Next times it starts in seconds.
   **Keep the black window open while you work.** Closing it stops the notebooks.

## Your key
`initial-analysis` and `map-explorer` ask for the **key** your teachers gave you. Paste it once. Your work is saved under it
and comes back whenever you use the same key, on any computer.

## Sharing your analyses (optional)
The first time you start, a page asks whether your analyses may be shared with the course, anonymised: only the analysis steps you
run, not your clicks. They are used to improve the course and for research on tools that support exploratory analysis. You answer once
and are not asked again. If you say no, everything works the same; your work just stays on your computer.

To change your mind, double-click **Change-my-answer** (`Change-my-answer.bat` on Windows, `Change-my-answer.command` on Mac, next to
`Start`). On a Mac, the first time, right-click it and choose **Open**, then **Open** again. If the notebooks are running, close their
black window first. The page then asks again.

## If something stops working
- A red message ("Failed to fetch", "Unauthorized", lost connection) or a page that does not respond: **reload the page**. Your work
  comes back as you left it. If the key is asked again, paste it again.
- The first start on a computer can take a minute or two ("Setting up the course tools"). Please wait and keep the black window open.
  After that it starts in seconds.
- Closed the black window by mistake? Start it again.

## Updates
Each time you start, the package fetches the latest notebooks by itself when you are online. You only ever need to
download this package again if the black window tells you so.

## The event logs
The folder `notebooks/data` holds the event logs, in the formats other tools read:
- Dhana loan application: `dhana-loan-application.xes`, `dhana-loan-application-molab.xes`, `dhana-loan-application.csv`
  (the notebooks themselves read `dhana-loan-application.parquet`, the same log in a format that loads in seconds).
- `Purchasing-Example.csv`, `SepsisCases2020EventLog.xes`.
