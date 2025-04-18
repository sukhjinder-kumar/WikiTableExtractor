#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import pandas as pd
from bs4 import BeautifulSoup
import argparse
import re
import os
import json
import logging
from urllib.parse import urlparse, urljoin
import io  # Needed for read_html from string
import shlex

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
HEADERS = {'User-Agent': 'WikipediaTableCleaner/1.1 (https://example.com/bot; myemail@example.com)'}
# !! Replace with your info !!

# --- Helper Functions ---

def fetch_html(url):
    """Fetches HTML content from a given URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        logging.info(f"Successfully fetched HTML from {url}")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None

def clean_text(text):
    """Cleans text extracted from table cells (can be used for metadata)."""
    if text is None:
        return None
    # Remove footnote references like [1], [a], etc.
    text = re.sub(r'\[[^\]]+\]', '', str(text))  # Ensure text is string
    # Strip leading/trailing whitespace
    text = text.strip()
    # Replace common 'empty' markers with None (pandas handles NaN)
    if text in ['—', '–', 'N/A', 'n/a', '']:
        return None
    return text

def extract_metadata(table_soup, base_url):
    """Extracts metadata from the table soup object and its surroundings."""
    metadata = {
        "caption": None,
        "source_url": base_url,
        "table_class": table_soup.get('class', [])
        # Add more metadata extraction as needed
        # "headers_units" might be harder to associate correctly after pd.read_html
    }

    # 1. Caption
    caption = table_soup.find('caption')
    if caption:
        metadata["caption"] = clean_text(caption.get_text())
        logging.info(f"Found caption: {metadata['caption']}")

    # Extract other metadata from table_soup if needed...

    return metadata

def clean_dataframe(df):
    """Applies cleaning operations AFTER a DataFrame has been created by pd.read_html."""
    if df is None or df.empty:
        return df

    # 1. Flatten MultiIndex columns if present
    #    We can flatten them or handle them as needed.
    #    Simple flattening: Join levels with a space
    if isinstance(df.columns, pd.MultiIndex):
        logging.info("Flattening MultiIndex columns")
        df.columns = [' '.join(map(str, col)).strip() for col in df.columns.values]

    # 2. Replace common 'empty' markers AFTER parsing
    #    (read_html might handle some, but good to be thorough)
    df.replace(['—', '–', 'N/A', 'n/a', ''], pd.NA, inplace=True)

    # 3. Attempt numeric conversion
    for col in df.columns:
        # Make a copy to attempt conversion
        original_col = df[col]
        try:
            # Try converting strings to numeric, coercing errors
            # Remove thousands separators, potentially currency symbols (basic example)
            cleaned_col = df[col].astype(str).str.replace(r'[,\$€£¥]', '', regex=True)
            numeric_col = pd.to_numeric(cleaned_col, errors='coerce')

            # Only assign back if conversion resulted in at least one number
            # and didn't convert everything to NaN (unless original was mostly non-numeric markers)
            if numeric_col.notna().any():  # or not original_col.isin(['—', '–', 'N/A', 'n/a', '', None]).all() :
                df[col] = numeric_col
                logging.debug(f"Attempted numeric conversion on column '{col}'.")
            else:
                logging.debug(f"Column '{col}' kept as object after numeric conversion attempt.")

        except Exception as e:
            logging.debug(f"Could not convert column '{col}': {e}")
            pass

    # 4. Drop rows/columns that are entirely NaN
    df.dropna(how='all', axis=0, inplace=True)
    df.dropna(how='all', axis=1, inplace=True)

    df.reset_index(drop=True, inplace=True)
    return df

def save_output(df, metadata, base_filename, index, output_format):
    """Saves the DataFrame to the specified format (CSV or JSON)."""
    filename = f"{base_filename}_table_{index + 1}.{output_format}"
    try:
        if output_format == 'csv':
            df.to_csv(filename, index=False, encoding='utf-8')
            logging.info(f"Table {index + 1} saved to {filename}")
            # Save metadata separately for CSV? Optional.
            # meta_filename = f"{base_filename}_table_{index + 1}_metadata.json"
            # with open(meta_filename, 'w', encoding='utf-8') as f:
            #     json.dump(metadata, f, indent=4)
            # logging.info(f"Metadata for table {index + 1} saved to {meta_filename}")
        elif output_format == 'json':
            output_data = {
                "metadata": metadata,
                # Convert NaN to None for JSON compatibility
                "data": df.where(pd.notna(df), None).to_dict(orient='records')
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            logging.info(f"Table {index + 1} (with metadata) saved to {filename}")

    except IOError as e:
        logging.error(f"Error saving file {filename}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during saving: {e}")

def process_page(args):
    """Process a single page given the argparse Namespace with parameters."""
    # Validate URL
    parsed_url = urlparse(args.url)
    if not all([parsed_url.scheme, parsed_url.netloc]):
        logging.error(f"Invalid URL provided: {args.url}")
        return

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    logging.info(f"Output directory set to: {args.output_dir}")

    # Determine base filename
    if args.name:
        base_filename = os.path.join(args.output_dir, args.name)
    else:
        path_part = parsed_url.path.strip('/').split('/')[-1]
        safe_filename = re.sub(r'[^\w\-]+', '_', path_part)
        base_filename = os.path.join(args.output_dir, safe_filename if safe_filename else "wikipedia_page")

    # Fetch HTML
    html_content = fetch_html(args.url)
    if not html_content:
        return

    # --- Parse tables using pandas.read_html ---
    dataframes = []
    try:
        logging.info(f"Attempting to parse tables with class '{args.css_class}' using pandas.read_html")
        dataframes = pd.read_html(io.StringIO(html_content),
                                  attrs={'class': args.css_class},
                                  flavor='bs4')
        logging.info(f"Found {len(dataframes)} table(s) matching class '{args.css_class}'.")
    except ValueError as e:
        logging.warning(f"No tables matching class '{args.css_class}' were found. Error: {e}")
        return
    except Exception as e:
        logging.error(f"Unexpected error during parsing: {e}")
        return

    # --- Extract Metadata using BeautifulSoup ---
    soup = BeautifulSoup(html_content, 'lxml')
    target_table_soups = soup.find_all('table', class_=args.css_class.split())
    if len(target_table_soups) != len(dataframes):
        logging.warning(f"Mismatch between BeautifulSoup ({len(target_table_soups)}) and pandas.read_html ({len(dataframes)}) table count. Proceeding with sequential pairing.")

    # --- Process and Save Each Table ---
    tables_processed_count = 0
    for i, (df, table_soup) in enumerate(zip(dataframes, target_table_soups)):
        logging.info(f"--- Processing Table {i + 1} ---")
        metadata = extract_metadata(table_soup, args.url)
        cleaned_df = clean_dataframe(df.copy())
        if cleaned_df is not None and not cleaned_df.empty:
            save_output(cleaned_df, metadata, base_filename, tables_processed_count, args.format)
            tables_processed_count += 1
        else:
            logging.warning(f"Skipping Table {i + 1} as it resulted in an empty DataFrame after cleaning.")

    logging.info(f"Finished processing. {tables_processed_count} out of {len(dataframes)} table(s) were saved.")

def create_arg_parser():
    """Creates and returns the argument parser."""
    parser = argparse.ArgumentParser(
        description="Scrape and clean tables from a Wikipedia page using pandas.read_html. Supports single URL or batch processing."
    )
    # Positional URL is optional if batch_file is provided.
    parser.add_argument("url", nargs="?", help="URL of the Wikipedia page")
    parser.add_argument("-o", "--output-dir", default=".", help="Directory to save the output files (default: current directory)")
    parser.add_argument("-f", "--format", choices=['csv', 'json'], default='csv', help="Output format (csv or json, default: csv)")
    parser.add_argument("-c", "--class", dest="css_class", default="wikitable", help="CSS class of the tables to scrape (default: 'wikitable')")
    parser.add_argument("-n", "--name", help="Base name for output files (default: derived from URL)")
    # New option for batch processing
    parser.add_argument("--batch-file", help="Path to a batch file with one URL (and flags) per line")
    return parser

def main():
    parser = create_arg_parser()
    args, remaining = parser.parse_known_args()

    # If a batch file is specified, process each line from the file
    if args.batch_file:
        if not os.path.isfile(args.batch_file):
            logging.error(f"Batch file not found: {args.batch_file}")
            return
        logging.info(f"Starting batch processing using file: {args.batch_file}")
        with open(args.batch_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        for line in lines:
            try:
                # Parse each line as separate command-line arguments.
                batch_args = parser.parse_args(shlex.split(line))
                logging.info(f"Processing URL: {batch_args.url}")
                process_page(batch_args)
            except Exception as e:
                logging.error(f"Error processing line: '{line}'. Exception: {e}")
    elif args.url:
        # Single URL mode
        process_page(args)
    else:
        parser.error("Please provide either a URL or a --batch-file.")

if __name__ == "__main__":
    main()
