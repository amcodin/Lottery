# You need to install requests and beautifulsoup4 for this script to work
# Run: pip install requests beautifulsoup4
import requests
from bs4 import BeautifulSoup
import os
import glob
from datetime import datetime, timedelta
from collections import Counter # Keep Counter for potential future use or if analyze_recurring_order is kept
import random # For potential tie-breaking or random selection within criteria
import re # Add import for regular expressions

# --- Configuration ---
STATS_URL = "https://australia.national-lottery.com/oz-lotto/statistics"
HTML_HISTORY_DIR = "html_history"
FILENAME_PREFIX = "oz_lotto_stats_"
FILENAME_DATE_FORMAT = "%Y-%m-%d"
DAYS_BETWEEN_DOWNLOADS = 7
OUTPUT_FILENAME = "output.txt"
NUMBERS_PER_ROW = 7 # Oz Lotto draws 7 main numbers

# --- Helper Functions ---

def ensure_dir(directory):
    """Creates the directory if it doesn't exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def download_html(url, filepath):
    """Downloads HTML content from a URL and saves it to a file."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'} # Be a polite scraper
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status() # Raise an exception for bad status codes
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Successfully downloaded and saved to {filepath}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False
    except IOError as e:
        print(f"Error saving file {filepath}: {e}")
        return False

def get_latest_file(directory, prefix, date_format):
    """Finds the most recent file in a directory matching a prefix and date format."""
    ensure_dir(directory)
    files = glob.glob(os.path.join(directory, f"{prefix}*.html"))
    if not files:
        return None, None

    latest_file = None
    latest_date = None
    for file in files:
        try:
            filename = os.path.basename(file)
            date_str = filename.replace(prefix, "").replace(".html", "")
            file_date = datetime.strptime(date_str, date_format)
            if latest_date is None or file_date > latest_date:
                latest_date = file_date
                latest_file = file
        except ValueError:
            # Ignore files that don't match the date format
            continue
    return latest_file, latest_date

def download_stats_if_needed(url, history_dir, prefix, date_format, days_interval):
    """Downloads the stats page if it hasn't been downloaded recently."""
    latest_file, latest_date = get_latest_file(history_dir, prefix, date_format)
    today = datetime.now().date()
    should_download = False

    if latest_date is None:
        print("No previous download found.")
        should_download = True
    else:
        print(f"Latest download found: {os.path.basename(latest_file)} from {latest_date.date()}")
        if (today - latest_date.date()) >= timedelta(days=days_interval):
            print(f"Latest download is {days_interval} or more days old.")
            should_download = True
        else:
            print("Latest download is recent enough.")

    if should_download:
        print(f"Attempting to download latest stats from {url}...")
        new_filename = f"{prefix}{today.strftime(date_format)}.html"
        new_filepath = os.path.join(history_dir, new_filename)
        if download_html(url, new_filepath):
            return new_filepath
        else:
            print("Download failed. Using latest available file if it exists.")
            return latest_file # Return the old file if download fails
    else:
        return latest_file


# --- Parsing Functions ---

def parse_table_data(table_element, expected_cols):
    """Generic function to parse data from a table. Tries to convert numbers."""
    data = []
    if not table_element:
        print("Warning: parse_table_data received None for table_element.")
        return data

    tbody = table_element.find('tbody')
    if not tbody:
        # Fallback as before
        rows = table_element.find_all('tr')
        if not rows: return data
    else:
        rows = tbody.find_all('tr')

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if row.find('th') or len(cells) != expected_cols:
             if not (len(cells) > 0 and cells[0].find('span', class_='ball')): continue

        row_data = [cell.get_text(strip=True) for cell in cells]
        balls_elements = row.find_all('span', class_='ball')
        balls = [span.get_text(strip=True) for span in balls_elements]

        # Try converting ball numbers and drawn counts to integers
        try:
            ball_int = int(balls[0]) if len(balls) == 1 else None
            balls_int = [int(b) for b in balls] if balls else []
        except (ValueError, TypeError):
            print(f"Warning: Could not convert ball number to int in row: {row_data}")
            ball_int = balls[0] if len(balls) == 1 else None # Keep as string if conversion fails
            balls_int = balls # Keep as strings

        item = {'raw_data': row_data} # Default structure

        # Structure known formats with integer conversion attempts
        if expected_cols == 3 and len(balls_int) == 1: # Hot, Least Often
             try:
                 drawn_count = int(row_data[1].replace(',', '')) # Remove commas if present
                 item = {'ball': ball_int, 'drawn': drawn_count, 'last_drawn_info': row_data[2]}
             except (ValueError, TypeError, IndexError):
                 item = {'ball': ball_int, 'drawn': row_data[1], 'last_drawn_info': row_data[2]} # Fallback
        elif expected_cols == 2 and len(balls_int) == 1: # Cold
             item = {'ball': ball_int, 'last_drawn_info': row_data[1]}
        elif expected_cols == 3 and len(balls_int) == 2: # Pairs
             try:
                 drawn_count = int(row_data[2].replace(',', ''))
                 item = {'balls': balls_int, 'drawn': drawn_count}
             except (ValueError, TypeError, IndexError):
                 item = {'balls': balls_int, 'drawn': row_data[2]} # Fallback
        elif expected_cols == 4 and len(balls_int) == 3: # Triplets
             try:
                 drawn_count = int(row_data[3].replace(',', ''))
                 item = {'balls': balls_int, 'drawn': drawn_count}
             except (ValueError, TypeError, IndexError):
                 item = {'balls': balls_int, 'drawn': row_data[3]} # Fallback
        else: # Fallback for unexpected structures
             item = {'balls': balls_int, 'raw_data': row_data}

        data.append(item)

    return data

def parse_numerical_order(soup):
    """Parses the 'Ordered by Ball Number' section. Tries to convert numbers."""
    data = []
    numeric_order_div = soup.find('div', id='numericOrder')
    if not numeric_order_div:
        print("Warning: 'numericOrder' div not found.")
        return data
    cells = numeric_order_div.find_all('div', class_='tableCell')
    for cell in cells:
        ball_text = cell.find('div', class_='ball').get_text(strip=True)
        drawn_text_element = cell.find(string=lambda t: 'Drawn:' in t if t else False)
        drawn_times_text = 'N/A'
        if drawn_text_element:
             strong_tag = drawn_text_element.find_next('strong')
             if strong_tag:
                 drawn_times_text = strong_tag.get_text(strip=True)

        # Try converting to integers
        try:
            ball_int = int(ball_text)
            drawn_int = int(drawn_times_text.replace(',', ''))
            data.append({'ball': ball_int, 'drawn': drawn_int})
        except (ValueError, TypeError):
            print(f"Warning: Could not convert numerical order data to int: ball='{ball_text}', drawn='{drawn_times_text}'")
            data.append({'ball': ball_text, 'drawn': drawn_times_text}) # Fallback to strings

    return data

def find_table_after_heading(soup, heading_text, heading_tag='h2', table_class='table'):
    """Finds the first table immediately following a specific heading."""
    heading = soup.find(heading_tag, string=lambda t: t and heading_text in t)
    if not heading:
        print(f"Warning: Heading '{heading_text}' not found.")
        return None
    # Find the next sibling table
    table = heading.find_next_sibling('table', class_=table_class)
    # Sometimes the table might be wrapped in a div
    if not table:
         parent_div = heading.find_parent('div', class_='box') # Common parent
         if parent_div:
              table = parent_div.find('table', class_=table_class) # Find first table within the box after heading? Risky.
              # Let's try finding the table directly after the heading's container if no direct sibling
              container = heading.parent
              table = container.find_next_sibling('table', class_=table_class)
              if not table: # Check within common parent structures
                   if container.name == 'div' and 'twoCol' in container.get('class', []):
                        table = container.find('table', class_=table_class)


    if not table:
         print(f"Warning: Table after heading '{heading_text}' not found.")

    return table

def find_table_in_div_after_heading(soup, heading_text, heading_tag='div', div_class='twoCol', table_class='table'):
     """Finds a table within a specific div structure following a heading-like element."""
     heading = soup.find(heading_tag, class_='h3', string=lambda t: t and heading_text in t)
     if not heading:
          print(f"Warning: Heading '{heading_text}' not found in specified structure.")
          return None
     parent_div = heading.find_parent('div', class_=div_class)
     if not parent_div:
          print(f"Warning: Could not find parent div '{div_class}' for heading '{heading_text}'.")
          return None
     table = parent_div.find('table', class_=table_class)
     if not table:
          print(f"Warning: Table not found within div for heading '{heading_text}'.")
     return table


# --- Original Analysis Function (Optional) ---
def analyze_recurring_order(data, subsequence_length=2):
    """
    Analyzes the frequency of recurring consecutive subsequences in a list of number sequences.
    (This function is from the original script and may or may not be needed depending on your goal)

    Args:
        data (list[list[int]]): A list where each inner list is a sequence of numbers.
        subsequence_length (int): The length of the subsequences to analyze (e.g., 2 for pairs).

    Returns:
        collections.Counter: A Counter object mapping subsequences (as tuples) to their frequency.
                           Returns an empty Counter if subsequence_length is invalid.
    """
    if subsequence_length <= 0:
        print("Error: Subsequence length must be greater than 0.")
        return Counter()
    if not data:
        print("Error: Input data is empty.")
        return Counter()

    all_subsequences = []
    for sequence in data:
        if not isinstance(sequence, list):
            print(f"Warning: Skipping invalid sequence format: {sequence}")
            continue
        if len(sequence) >= subsequence_length:
            # Generate sliding windows
            for i in range(len(sequence) - subsequence_length + 1):
                # Convert subsequence to tuple to be hashable for Counter
                try:
                    # Ensure elements are integers for consistent typing
                    subsequence = tuple(int(x) for x in sequence[i : i + subsequence_length])
                    all_subsequences.append(subsequence)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Skipping subsequence due to non-numeric data: {sequence[i : i + subsequence_length]} in {sequence} - {e}")

    return Counter(all_subsequences)


# --- Number Selection Logic ---

def get_numbers_by_frequency(numerical_data, count, highest=True):
    """Gets top 'count' numbers sorted by frequency."""
    valid_data = [item for item in numerical_data if isinstance(item.get('drawn'), int) and isinstance(item.get('ball'), int)]
    if not valid_data:
        print("Warning: No valid numerical data with integer counts found for frequency sorting.")
        return []

    # Sort primarily by frequency, secondarily by ball number for stable sort
    sorted_data = sorted(valid_data, key=lambda x: (x['drawn'], x['ball']), reverse=highest)
    return [item['ball'] for item in sorted_data[:count]]

def get_numbers_by_overdue(cold_data, count):
    """Gets top 'count' overdue numbers, parsing 'days ago' for sorting."""
    # Function to extract 'days ago' from the info string
    def extract_days(info_str):
        if not isinstance(info_str, str):
            return 9999 # Treat non-strings as least overdue
        match = re.search(r'(\d+)\s+days? ago', info_str)
        if match:
            return int(match.group(1))
        # Fallback: If no days found, return a large number to place it lower in overdue sort
        # Consider other patterns if needed (e.g., 'drawn yesterday')
        return 9999

    valid_data = []
    for item in cold_data:
        ball = item.get('ball')
        last_info = item.get('last_drawn_info')
        if isinstance(ball, int) and last_info:
             days_ago = extract_days(last_info)
             valid_data.append({'ball': ball, 'days_ago': days_ago})
        elif isinstance(ball, int):
             # If last_info is missing, treat as very low priority (not overdue)
             valid_data.append({'ball': ball, 'days_ago': 0})


    if not valid_data:
        print("Warning: No valid cold data with integer ball numbers found.")
        return []

    # Sort by days_ago (descending - most days ago first), then ball number for stability
    sorted_data = sorted(valid_data, key=lambda x: (x['days_ago'], x['ball']), reverse=True)
    
    # Return only the unique ball numbers up to the requested count
    unique_balls = []
    seen_balls = set()
    for item in sorted_data:
        if item['ball'] not in seen_balls:
            unique_balls.append(item['ball'])
            seen_balls.add(item['ball'])
            if len(unique_balls) == count:
                break
                
    return unique_balls

def get_numbers_by_least_frequent(least_frequent_data, count):
    """Gets top 'count' least frequent numbers."""
    # Use the same logic as get_numbers_by_frequency but reverse the sort order
    valid_data = [item for item in least_frequent_data if isinstance(item.get('drawn'), int) and isinstance(item.get('ball'), int)]
    if not valid_data:
        print("Warning: No valid least frequent data with integer counts found.")
        return []

    # Sort primarily by frequency (ascending), secondarily by ball number
    sorted_data = sorted(valid_data, key=lambda x: (x['drawn'], x['ball']))
    return [item['ball'] for item in sorted_data[:count]]


def select_unique_combination(list1, count1, list2, count2, total_needed):
    """Combines numbers from two lists, ensuring unique results up to total_needed."""
    selected = []
    pool1 = list(list1) # Make copies to avoid modifying originals
    pool2 = list(list2)

    # Take initial numbers from pool1
    added_count = 0
    idx1 = 0
    while added_count < count1 and idx1 < len(pool1):
        num = pool1[idx1]
        if num not in selected:
            selected.append(num)
            added_count += 1
        idx1 += 1

    # Add numbers from pool2
    added_count = 0
    idx2 = 0
    while len(selected) < total_needed and added_count < count2 and idx2 < len(pool2):
         num = pool2[idx2]
         if num not in selected:
              selected.append(num)
         # Always increment idx2 to move through pool2, even if num was duplicate
         idx2 +=1 
         # Only count additions towards the count2 limit if unique
         if num not in selected[:-1]: # Check if it was actually added
              added_count +=1

    # If still not enough, fill remaining from pool1 (beyond the initial count1)
    while len(selected) < total_needed and idx1 < len(pool1):
         num = pool1[idx1]
         if num not in selected:
              selected.append(num)
         idx1 += 1

    # If *still* not enough, fill remaining from pool2 (beyond the initial count2)
    while len(selected) < total_needed and idx2 < len(pool2):
         num = pool2[idx2]
         if num not in selected:
              selected.append(num)
         idx2 += 1

    # Final check - return exactly total_needed unique numbers if possible
    # If we couldn't reach total_needed, return what we have
    return list(set(selected))[:total_needed]


# --- Output Generation ---

def generate_output_rows(stats, num_rows=6, numbers_per_row=NUMBERS_PER_ROW):
    """Generates rows of numbers based on extracted statistics."""
    rows = []
    used_numbers_global = set() # Keep track of numbers used in primary rows (1, 2, 3)

    # Prepare sorted lists (get more than needed initially - e.g., 50)
    fetch_count = 50 # Increased fetch count
    most_common_all = get_numbers_by_frequency(stats.get('numerical', []), fetch_count, highest=True)
    most_overdue_all = get_numbers_by_overdue(stats.get('cold', []), fetch_count)
    least_common_all = get_numbers_by_least_frequent(stats.get('least_often', []), fetch_count)

    # Basic validation
    if not most_common_all or len(most_common_all) < numbers_per_row:
        print(f"Error: Insufficient most common numbers ({len(most_common_all)}) to generate rows.") ; return []
    # Validation for others happens as rows are generated

    # Row 1: Top N Most Common
    row1 = most_common_all[:numbers_per_row]
    if len(row1) == numbers_per_row: 
        rows.append(sorted(row1))
        used_numbers_global.update(row1)
        print("Generated Row 1 (Most Common)")
    else: 
        print(f"Warning: Could not generate Row 1 with exactly {numbers_per_row} numbers. Aborting.")
        return [] # Cannot proceed without Row 1


    # Row 2: Top N Most Overdue (Cold), filled with next common if needed
    row2_base = get_numbers_by_overdue(stats.get('cold', []), numbers_per_row)
    row2 = list(row2_base) # Start with the overdue numbers found
    needed_more_r2 = numbers_per_row - len(row2)
    
    if needed_more_r2 > 0:
        print(f"Row 2: Found only {len(row2)} unique overdue numbers. Filling {needed_more_r2} slots with next common.")
        # Find next common numbers NOT used in Row 1 and NOT already in row2_base
        fill_candidates_r2 = [num for num in most_common_all[numbers_per_row:] if num not in used_numbers_global and num not in row2]
        fill_count_r2 = 0
        for num in fill_candidates_r2:
            if len(row2) < numbers_per_row:
                row2.append(num)
                fill_count_r2 += 1
            else:
                break
        if fill_count_r2 < needed_more_r2:
             print(f"Warning: Row 2 could only be filled to {len(row2)} numbers after trying next common.")

    if len(row2) == numbers_per_row: 
        rows.append(sorted(row2))
        used_numbers_global.update(row2) # Add row 2 numbers to global used set
        print("Generated Row 2 (Most Overdue / Filled)")
    else: 
        print(f"Warning: Could not generate Row 2 (Most Overdue / Filled) with exactly {numbers_per_row} unique numbers (got {len(row2)}). Skipping row.")
        # Decide if we should abort or continue? For now, continue.


    # Row 3: Next N Most Common (e.g., ranks 8-14 if numbers_per_row is 7)
    start_index_r3 = numbers_per_row
    end_index_r3 = numbers_per_row * 2
    row3_candidates = [num for num in most_common_all[start_index_r3:end_index_r3] if num not in used_numbers_global] # Exclude globally used
    row3 = row3_candidates[:numbers_per_row] # Take the first N available
    
    # If not enough unique candidates, fill with next available common
    needed_more_r3 = numbers_per_row - len(row3)
    if needed_more_r3 > 0:
         print(f"Row 3: Found only {len(row3)} unique numbers in ranks {start_index_r3+1}-{end_index_r3}. Filling {needed_more_r3} slots with next common.")
         fill_candidates_r3 = [num for num in most_common_all[end_index_r3:] if num not in used_numbers_global and num not in row3]
         for num in fill_candidates_r3:
              if len(row3) < numbers_per_row:
                   row3.append(num)
              else:
                   break

    if len(row3) == numbers_per_row: 
        rows.append(sorted(row3))
        used_numbers_global.update(row3) # Add row 3 numbers to global used set
        print("Generated Row 3 (Next Most Common / Filled)")
    else: 
        print(f"Warning: Could not generate Row 3 (Next Most Common) with exactly {numbers_per_row} unique numbers (got {len(row3)}). Skipping row.")


    # Row 4: Mix Hot/Cold (e.g., 4 Hot + 3 Cold)
    count1_r4 = 4
    count2_r4 = 3
    # Use the full lists, let select_unique_combination handle uniqueness
    hot_candidates_r4 = most_common_all
    cold_candidates_r4 = most_overdue_all
    if len(hot_candidates_r4) >= count1_r4 and len(cold_candidates_r4) >= count2_r4:
        row4 = select_unique_combination(hot_candidates_r4, count1_r4, cold_candidates_r4, count2_r4, numbers_per_row)
        if len(row4) == numbers_per_row: 
            rows.append(sorted(row4))
            print("Generated Row 4 (Mix Hot/Cold)")
        else: 
            print(f"Warning: Could not generate Row 4 (Mix Hot/Cold) with exactly {numbers_per_row} unique numbers (got {len(row4)}). Skipping row.")
    else:
        print(f"Warning: Insufficient base numbers for Row 4 (Mix Hot/Cold). Need {count1_r4} hot ({len(hot_candidates_r4)} avail), {count2_r4} cold ({len(cold_candidates_r4)} avail). Skipping row.")

    # Row 5: Mix Next Hot/Cold (e.g., Hot ranks 5-8 + Cold ranks 4-6)
    start_hot_r5 = count1_r4 # Start after the ones potentially used in Row 4
    count_hot_r5 = 4
    start_cold_r5 = count2_r4 # Start after the ones potentially used in Row 4
    count_cold_r5 = 3
    hot_r5_candidates = most_common_all[start_hot_r5:] 
    cold_r5_candidates = most_overdue_all[start_cold_r5:]
    if len(hot_r5_candidates) >= count_hot_r5 and len(cold_r5_candidates) >= count_cold_r5:
        row5 = select_unique_combination(hot_r5_candidates, count_hot_r5, cold_r5_candidates, count_cold_r5, numbers_per_row)
        if len(row5) == numbers_per_row: 
            rows.append(sorted(row5))
            print("Generated Row 5 (Mix Next Hot/Cold)")
        else: 
            print(f"Warning: Could not generate Row 5 (Mix Next Hot/Cold) with exactly {numbers_per_row} unique numbers (got {len(row5)}). Skipping row.")
    else:
         print(f"Warning: Insufficient candidate numbers for Row 5 (Mix Next Hot/Cold). Need {count_hot_r5} more hot ({len(hot_r5_candidates)} avail), {count_cold_r5} more cold ({len(cold_r5_candidates)} avail). Skipping row.")

    # Row 6: Mix Least Common/Hot (e.g., 4 Least Common + 3 Hot)
    count1_r6 = 4
    count2_r6 = 3
    least_common_candidates_r6 = least_common_all
    hot_candidates_r6 = most_common_all
    if not least_common_candidates_r6 or len(least_common_candidates_r6) < count1_r6:
         print(f"Warning: Insufficient least common numbers ({len(least_common_candidates_r6)}) for Row 6. Need {count1_r6}. Skipping row.")
    elif len(hot_candidates_r6) < count2_r6:
         print(f"Warning: Insufficient most common numbers ({len(hot_candidates_r6)}) for Row 6. Need {count2_r6}. Skipping row.")
    else:
        row6 = select_unique_combination(least_common_candidates_r6, count1_r6, hot_candidates_r6, count2_r6, numbers_per_row)
        if len(row6) == numbers_per_row: 
            rows.append(sorted(row6))
            print("Generated Row 6 (Mix Least Common/Hot)")
        else: 
            print(f"Warning: Could not generate Row 6 (Mix Least Common/Hot) with exactly {numbers_per_row} unique numbers (got {len(row6)}). Skipping row.")

    # Return only the successfully generated rows
    print(f"Successfully generated {len(rows)} rows in total.")
    return rows # Return whatever was successfully generated


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Oz Lotto Statistics Analysis...")

    # 1. Get the latest HTML data
    latest_html_file = download_stats_if_needed(
        STATS_URL, HTML_HISTORY_DIR, FILENAME_PREFIX, FILENAME_DATE_FORMAT, DAYS_BETWEEN_DOWNLOADS
    )

    if not latest_html_file or not os.path.exists(latest_html_file):
        print("Error: Could not find or download HTML statistics file. Trying fallback...")
        attached_file = 'c:\\Users\\Owner\\Documents\\2025\\Lottery\\Oz Lotto Statistics, Number Frequencies & Most Drawn.html'
        if os.path.exists(attached_file):
             print(f"Attempting to use attached file: {attached_file}")
             latest_html_file = attached_file
        else:
             print("Error: Fallback file not found. Exiting.")
             exit()

    # 2. Read and parse the HTML
    try:
        with open(latest_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        print(f"Parsing data from: {latest_html_file}")
    except Exception as e:
        print(f"Error reading or parsing HTML file {latest_html_file}: {e}")
        exit()

    # 3. Extract specific sections into a dictionary
    extracted_stats = {}

    # Hot Numbers (used for reference, main frequency from numerical)
    hot_numbers_table = find_table_after_heading(soup, "Hot Numbers (Most Common)")
    extracted_stats['hot'] = parse_table_data(hot_numbers_table, expected_cols=3) if hot_numbers_table else []

    # Ordered by Ball Number (Primary source for frequency)
    extracted_stats['numerical'] = parse_numerical_order(soup)

    # Cold Numbers
    cold_numbers_table = find_table_after_heading(soup, "Cold Numbers (Most Overdue)")
    extracted_stats['cold'] = parse_table_data(cold_numbers_table, expected_cols=2) if cold_numbers_table else []

    # Least Often Picked
    least_often_table = find_table_after_heading(soup, "Least Often Picked Numbers", heading_tag='div')
    extracted_stats['least_often'] = parse_table_data(least_often_table, expected_cols=3) if least_often_table else []

    # Pairs/Triplets (Optional: print or use in advanced strategies)
    common_pairs_table = find_table_in_div_after_heading(soup, "Most Common Pairs")
    extracted_stats['pairs'] = parse_table_data(common_pairs_table, expected_cols=3) if common_pairs_table else []
    consec_pairs_table = find_table_in_div_after_heading(soup, "Most Common Consecutive Pairs")
    extracted_stats['consec_pairs'] = parse_table_data(consec_pairs_table, expected_cols=3) if consec_pairs_table else []
    common_triplets_table = find_table_in_div_after_heading(soup, "Most Common Triplets")
    extracted_stats['triplets'] = parse_table_data(common_triplets_table, expected_cols=4) if common_triplets_table else []
    consec_triplets_table = find_table_in_div_after_heading(soup, "Most Common Consecutive Triplets")
    extracted_stats['consec_triplets'] = parse_table_data(consec_triplets_table, expected_cols=4) if consec_triplets_table else []

    # Print extracted data (optional)
    print("\n--- Extracted Statistics Summary ---")
    print(f"Hot Numbers found: {len(extracted_stats.get('hot', []))}")
    print(f"Numerical Order entries found: {len(extracted_stats.get('numerical', []))}")
    print(f"Cold Numbers found: {len(extracted_stats.get('cold', []))}")
    print(f"Least Often Picked found: {len(extracted_stats.get('least_often', []))}")
    # Add prints for pairs/triplets if desired

    # 4. Generate Output Rows
    print(f"\n--- Generating {OUTPUT_FILENAME} ---")
    output_rows = generate_output_rows(extracted_stats, num_rows=6, numbers_per_row=NUMBERS_PER_ROW)

    # 5. Write to output file
    if output_rows:
        # Check if we generated the desired number of rows (6) before writing
        if len(output_rows) == 6: # Use the literal value 6 here
            try:
                with open(OUTPUT_FILENAME, 'w') as f:
                    f.write(f"# Oz Lotto Number Suggestions based on stats from {os.path.basename(latest_html_file)}\n")
                    f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("# Row 1: Most Common (Top 7 Freq)\n")
                    f.write("# Row 2: Most Overdue (Top 7 Coldest)\n")
                    f.write("# Row 3: Next Most Common (Freq Ranks 8-14)\n")
                    f.write("# Row 4: Mix Hot/Cold (Top 4 Freq / Top 3 Cold)\n")
                    f.write("# Row 5: Mix Next Hot/Cold (Next 4 Freq / Next 3 Cold)\n")
                    f.write("# Row 6: Mix Least Common/Hot (Top 4 Least Freq / Top 3 Freq)\n\n")
                    for i, row in enumerate(output_rows):
                        row_str = ", ".join(map(str, sorted(row))) # Ensure sorted output
                        f.write(f"Row {i+1}: {row_str}\n")
                print(f"Successfully wrote {len(output_rows)} rows to {OUTPUT_FILENAME}")
            except IOError as e:
                print(f"Error writing to output file {OUTPUT_FILENAME}: {e}")
        else:
             # This message is now more accurate as generate_output_rows returns only good rows
             print(f"Error: Generated {len(output_rows)} rows, but 6 were required. Not writing to {OUTPUT_FILENAME}.") # Use 6 here too
             print("Check warnings above for reasons why specific rows might have failed (e.g., insufficient unique numbers).")

    else:
        print("Could not generate any output rows based on the available data.")


    print("\nAnalysis complete.")