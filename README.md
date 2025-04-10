# Wikipedia Table Extractor

This script scrapes tables from Wikipedia pages and saves them as either CSV or JSON files. It allows you to specify the URL of the Wikipedia page and the CSS class of the tables you are interested in. The script also performs basic data cleaning to make the extracted tables more usable.

## What does this project do?

The Wikipedia Table Extractor automates the process of extracting tabular data from Wikipedia articles. It fetches the HTML content of a given Wikipedia page, identifies tables based on their CSS class (defaulting to `wikitable`), and then parses these tables into structured data formats (CSV or JSON). The script also includes functionality to clean the extracted data by removing footnote references, handling empty cells, and attempting to convert numeric columns to the correct data type.

## Code Methodology

The script follows these steps:

1.  **Configuration:** Sets up logging for informational messages and errors, and defines a default User-Agent header for making HTTP requests to Wikipedia. **Important:** You should replace the example User-Agent with your own information as indicated in the code.
2.  **Fetching HTML:** The `Workspace_html` function uses the `requests` library to download the HTML content from the specified URL. It includes error handling for network issues.
3.  **Metadata Extraction:** The `extract_metadata` function uses `BeautifulSoup` to parse the HTML and extract metadata associated with the tables, such as the caption, source URL, and CSS classes.
4.  **Table Parsing:** The core of the table extraction is done using the `pandas.read_html` function. This function can directly parse HTML tables into pandas DataFrames. The script filters tables based on the provided CSS class.
5.  **Data Cleaning:** The `clean_dataframe` function performs several cleaning operations on the extracted DataFrames:
    * Flattens multi-level column headers that might arise from `colspan` or `rowspan` attributes.
    * Replaces common empty cell markers (like '—', 'N/A') with pandas' `NA` value.
    * Attempts to convert columns containing numeric data (after removing commas and currency symbols) to numeric types.
    * Drops rows and columns that are entirely empty after cleaning.
6.  **Saving Output:** The `save_output` function saves the cleaned DataFrame to a file. It supports two output formats:
    * **CSV:** Saves the DataFrame to a CSV file.
    * **JSON:** Saves the DataFrame along with the extracted metadata to a JSON file.
7.  **Command-Line Interface:** The script uses `argparse` to provide a command-line interface, allowing users to specify the URL, output directory, output format, table CSS class, and a base name for the output files.

## Demonstration Script

To run the script, you need to have Python 3 installed along with the required libraries (`requests`, `pandas`, `beautifulsoup4`, `html5lib`). You can install them using pip:

```bash
pip3 install requests pandas beautifulsoup4 lxml html5lib
```

A sample script is `python3 wiki_table_cleaner.py https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_India -o output -f json -n india_heritage_sites`
