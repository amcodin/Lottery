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
TOTAL_NUMBERS = 47 # Oz Lotto pool size

# --- Number Generation Weights ---
# Adjust these to change the bias in probabilistic selection
BASE_WEIGHT = 1.0
FREQUENCY_MULTIPLIER = 0.5 # How much frequency affects weight (relative to base)
OVERDUE_BONUS = 10.0      # Flat bonus weight for top N overdue numbers
NUM_OVERDUE_CONSIDERED = 10 # How many top overdue numbers get the bonus

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
        # Use os.path.basename only if latest_file is not None
        if latest_file:
             print(f"Latest download found: {os.path.basename(latest_file)} from {latest_date.date()}")
        else:
             print(f"Latest download date found ({latest_date.date()}), but file path is missing. Will attempt download.")
             should_download = True # Treat missing file path as needing download

        if not should_download and (today - latest_date.date()) >= timedelta(days=days_interval):
            print(f"Latest download is {days_interval} or more days old.")
            should_download = True
        elif not should_download:
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
            # print(f"Warning: Could not convert ball number to int in row: {row_data}") # Reduce noise
            ball_int = balls[0] if len(balls) == 1 else None # Keep as string if conversion fails
            balls_int = balls # Keep as strings

        item = {'raw_data': row_data} # Default structure

        # Structure known formats with integer conversion attempts
        if expected_cols == 3 and len(balls_int) == 1 and ball_int is not None: # Hot, Least Often
             try:
                 drawn_count = int(row_data[1].replace(',', '')) # Remove commas if present
                 item = {'ball': ball_int, 'drawn': drawn_count, 'last_drawn_info': row_data[2]}
             except (ValueError, TypeError, IndexError):
                 item = {'ball': ball_int, 'drawn': row_data[1], 'last_drawn_info': row_data[2]} # Fallback
        elif expected_cols == 2 and len(balls_int) == 1 and ball_int is not None: # Cold
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
             # Ensure balls_int contains integers if possible, else strings
             processed_balls = []
             for b in balls_int:
                 try:
                     processed_balls.append(int(b))
                 except (ValueError, TypeError):
                     processed_balls.append(b) # Keep original if not convertible
             item = {'balls': processed_balls, 'raw_data': row_data}


        # Only add if we successfully structured it or it's a fallback with balls
        if 'ball' in item or 'balls' in item:
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
        ball_element = cell.find('div', class_='ball')
        if not ball_element: continue # Skip if no ball element
        ball_text = ball_element.get_text(strip=True)

        drawn_text_element = cell.find(string=lambda t: 'Drawn:' in t if t else False)
        drawn_times_text = '0' # Default to 0 if not found
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
            # Fallback to strings or skip? Let's try to keep the ball number if possible
            try:
                 ball_int = int(ball_text)
                 data.append({'ball': ball_int, 'drawn': 0}) # Assign 0 frequency if count fails
            except (ValueError, TypeError):
                 continue # Skip if ball number itself is invalid

    return data

def find_table_after_heading(soup, heading_text, heading_tag='h2', table_class='table'):
    """Finds the first table immediately following a specific heading."""
    heading = soup.find(heading_tag, string=lambda t: t and heading_text in t)
    if not heading:
        # Try finding heading within common parent structures if direct find fails
        possible_parents = soup.find_all(['div', 'section']) # Common containers
        for parent in possible_parents:
             heading = parent.find(heading_tag, string=lambda t: t and heading_text in t)
             if heading: break # Found it

    if not heading:
        # print(f"Warning: Heading '{heading_text}' not found.") # Reduce noise
        return None

    # Find the next sibling table
    table = heading.find_next_sibling('table', class_=table_class)

    # If no direct sibling, search within parent containers more robustly
    if not table:
        current = heading
        while current.parent:
            # Check siblings of the current element's container
            container = current.parent
            table = container.find_next_sibling('table', class_=table_class)
            if table: break

            # Check within the container itself (sometimes heading and table are siblings inside a div)
            table = heading.find_next('table', class_=table_class)
            if table: break

            # Check within common parent structures like 'box' or 'twoCol' relative to heading's parent
            parent_div = heading.find_parent('div', class_='box')
            if parent_div:
                table = parent_div.find('table', class_=table_class)
                if table: break

            parent_twoCol = heading.find_parent('div', class_='twoCol')
            if parent_twoCol:
                 table = parent_twoCol.find('table', class_=table_class)
                 if table: break

            current = container # Move up the tree

    if not table:
         # print(f"Warning: Table after heading '{heading_text}' not found.") # Reduce noise
         pass

    return table

def find_table_in_div_after_heading(soup, heading_text, heading_tag='div', div_class='twoCol', table_class='table'):
     """Finds a table within a specific div structure following a heading-like element."""
     # Find the heading first (might be h3 or similar inside the target div)
     target_div = None
     possible_headings = soup.find_all(['h2', 'h3', 'div'], string=lambda t: t and heading_text in t)

     for h in possible_headings:
         # Check if this heading is inside the desired div structure
         parent_div = h.find_parent('div', class_=div_class)
         if parent_div:
             # Check if the heading is specifically the one we look for (e.g., class h3)
             if h.name == heading_tag or (heading_tag == 'div' and 'h3' in h.get('class', [])):
                  target_div = parent_div
                  break # Found the right structure

     if not target_div:
          # print(f"Warning: Could not find parent div '{div_class}' containing heading '{heading_text}'.") # Reduce noise
          return None

     table = target_div.find('table', class_=table_class)
     if not table:
          # print(f"Warning: Table not found within div for heading '{heading_text}'.") # Reduce noise
          pass
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
              # Only count additions towards the count2 limit if unique
              added_count +=1
         # Always increment idx2 to move through pool2, even if num was duplicate
         idx2 +=1


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

def generate_probabilistic_row(stats, num_needed=NUMBERS_PER_ROW):
    """Generates a row of numbers using weighted random selection based on stats."""
    print("Generating Row 1 (Probabilistic Weighted)...")
    numerical_data = stats.get('numerical', [])
    cold_data = stats.get('cold', [])

    if not numerical_data:
        print("Error: Cannot generate probabilistic row without numerical frequency data. Falling back to random.")
        return sorted(random.sample(range(1, TOTAL_NUMBERS + 1), num_needed))

    # 1. Create frequency map
    freq_map = {item['ball']: item['drawn'] for item in numerical_data if isinstance(item.get('ball'), int) and isinstance(item.get('drawn'), int)}

    # 2. Identify top overdue balls
    top_overdue = get_numbers_by_overdue(cold_data, NUM_OVERDUE_CONSIDERED)

    # 3. Calculate weights
    weights = {}
    all_balls = list(range(1, TOTAL_NUMBERS + 1))
    total_weight = 0
    for ball in all_balls:
        weight = BASE_WEIGHT
        # Add frequency bonus
        frequency = freq_map.get(ball, 0)
        weight += frequency * FREQUENCY_MULTIPLIER
        # Add overdue bonus
        if ball in top_overdue:
            weight += OVERDUE_BONUS
        
        # Ensure weight is not negative (shouldn't happen with current logic)
        weights[ball] = max(0.1, weight) # Use a small minimum weight
        total_weight += weights[ball]
        
    # Handle case where total_weight is zero (e.g., all data invalid)
    if total_weight <= 0:
        print("Error: Total weight is zero. Falling back to random selection.")
        return sorted(random.sample(all_balls, num_needed))

    # 4. Normalize weights (optional but good practice for understanding probabilities)
    # probabilities = {ball: w / total_weight for ball, w in weights.items()}

    # 5. Select numbers
    selected_numbers = set()
    population = list(weights.keys())
    weight_values = list(weights.values())

    # Pick slightly more than needed to increase chance of getting unique numbers quickly
    sample_size = num_needed * 3
    try:
        weighted_sample = random.choices(population, weights=weight_values, k=sample_size)
    except ValueError as e:
         print(f"Error during random.choices (weights might be invalid): {e}. Falling back to random.")
         return sorted(random.sample(all_balls, num_needed))


    # Extract unique numbers from the weighted sample
    for num in weighted_sample:
        if len(selected_numbers) < num_needed:
            selected_numbers.add(num)
        else:
            break

    # 6. Fill if necessary (unlikely with k=num_needed*3 but possible)
    needed_more = num_needed - len(selected_numbers)
    if needed_more > 0:
        print(f"Probabilistic selection yielded {len(selected_numbers)} unique numbers. Filling {needed_more} randomly.")
        remaining_population = [ball for ball in all_balls if ball not in selected_numbers]
        try:
            random_fill = random.sample(remaining_population, needed_more)
            selected_numbers.update(random_fill)
        except ValueError:
             print(f"Error: Not enough remaining numbers ({len(remaining_population)}) to fill the row.")
             # Return what we have, even if incomplete
             return sorted(list(selected_numbers))


    return sorted(list(selected_numbers))

def generate_overdue_frequency_row(stats, num_needed=NUMBERS_PER_ROW):
    """
    Weighted approach focusing on how long a ball is overdue, with smaller emphasis on frequency.
    Normalizes both metrics to avoid extreme weight disparities.
    """
    cold_data = stats.get('cold', [])
    numerical_data = stats.get('numerical', [])

    # Build maps
    freq_map = {
        item['ball']: item['drawn']
        for item in numerical_data
        if isinstance(item.get('ball'), int) and isinstance(item.get('drawn'), int)
    }

    def extract_days(info_str):
        if not isinstance(info_str, str):
            return 0
        m = re.search(r'(\d+)\s+days? ago', info_str)
        return int(m.group(1)) if m else 0

    overdue_map = {
        item['ball']: extract_days(item.get('last_drawn_info', ''))
        for item in cold_data
        if isinstance(item.get('ball'), int)
    }

    # Handle empty cases
    all_balls = list(range(1, TOTAL_NUMBERS + 1))
    if not overdue_map and not freq_map:
        return sorted(random.sample(all_balls, num_needed))

    # Normalize metrics
    max_days = max(overdue_map.values(), default=0) or 1
    max_freq = max(freq_map.values(), default=0) or 1

    OVERDUE_WEIGHT = 2.0
    FREQ_WEIGHT = 0.2
    BASE_MIN_WEIGHT = 0.1

    # Compute weights
    weights = []
    for b in all_balls:
        days_norm = overdue_map.get(b, 0) / max_days
        freq_norm = freq_map.get(b, 0) / max_freq
        w = OVERDUE_WEIGHT * days_norm + FREQ_WEIGHT * freq_norm + BASE_MIN_WEIGHT
        weights.append(w)

    # Sample and dedupe
    try:
        picks = random.choices(all_balls, weights=weights, k=num_needed * 3)
    except Exception:
        return sorted(random.sample(all_balls, num_needed))

    selected = []
    for p in picks:
        if p not in selected:
            selected.append(p)
            if len(selected) == num_needed:
                break

    # Fallback fill with top overdue if needed
    if len(selected) < num_needed:
        by_overdue = sorted(all_balls,
                            key=lambda x: overdue_map.get(x, 0),
                            reverse=True)
        for b in by_overdue:
            if b not in selected:
                selected.append(b)
            if len(selected) == num_needed:
                break

    return sorted(selected)


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

    # --- Row 1: Probabilistic Weighted Selection ---
    row1 = generate_probabilistic_row(stats, numbers_per_row)
    if len(row1) == numbers_per_row:
        rows.append(sorted(row1)) # Already sorted by generate_probabilistic_row
        used_numbers_global.update(row1)
        # print("Generated Row 1 (Probabilistic Weighted)") # Message printed inside function
    else:
        print(f"Warning: Could not generate Row 1 (Probabilistic) with exactly {numbers_per_row} numbers (got {len(row1)}). Aborting.")
        return [] # Cannot proceed without Row 1


    # --- Row 2: Weighted Overdue-based approach ---
    row2 = generate_overdue_frequency_row(stats, numbers_per_row)
    if len(row2) == numbers_per_row:
        rows.append(row2)
        used_numbers_global.update(row2)
        print("Generated Row 2 (Weighted Overdue)")
    else:
        print(f"Warning: Could not generate Row 2 (Weighted Overdue) with exactly {numbers_per_row} unique numbers (got {len(row2)}). Skipping row.")

    # --- Row 3: Next N Most Common with probabilistic weighting ---
    row3_candidates = [num for num in most_common_all if num not in used_numbers_global]
    if not row3_candidates:
        print("Warning: No candidates available for Row 3. Skipping row.")
    else:
        # build a frequency map for weighting
        freq_map = {item['ball']: item['drawn'] for item in stats.get('numerical', [])}
        # prepare parallel weight list (use count=1 if missing)
        weights = [freq_map.get(num, 1) for num in row3_candidates]
        selected = []
        # weighted sampling without replacement
        try:
            import random
            temp_cands = list(row3_candidates)
            temp_weights = list(weights)
            while len(selected) < numbers_per_row and temp_cands:
                pick = random.choices(temp_cands, weights=temp_weights, k=1)[0]
                selected.append(pick)
                idx = temp_cands.index(pick)
                temp_cands.pop(idx)
                temp_weights.pop(idx)
        except Exception as e:
            print(f"Warning: Weighted sampling failed ({e}), falling back to simple slice.")
            selected = row3_candidates[:numbers_per_row]

        # fill any remaining slots uniformly at random
        if len(selected) < numbers_per_row:
            remaining = [n for n in range(1, TOTAL_NUMBERS+1) if n not in used_numbers_global and n not in selected]
            try:
                fill = random.sample(remaining, numbers_per_row - len(selected))
                selected.extend(fill)
            except Exception:
                pass

        if len(selected) == numbers_per_row:
            row3 = sorted(selected)
            rows.append(row3)
            used_numbers_global.update(row3)
            print("Generated Row 3 (Probabilistic Next Most Common)")
        else:
            print(f"Warning: Could not generate Row 3 with {numbers_per_row} nums (got {len(selected)}). Skipping row.")

    # --- Row 4: Mix Hot/Cold (Probabilistic 3 Hot + 3 Cold + 1 Fill based on ≈1/57 probability) ---
    count1_r4 = 3  # Target 3 hot
    count2_r4 = 3  # Target 3 cold
    pool_size_r4 = 15 # Define the size of the candidate pools for sampling

    # Get candidate pools (more than needed for sampling)
    hot_pool_r4 = most_common_all[:pool_size_r4]
    cold_pool_r4 = most_overdue_all[:pool_size_r4]

    if len(hot_pool_r4) < count1_r4 or len(cold_pool_r4) < count2_r4:
        print(f"Warning: Insufficient candidates for Row 4 pools (need {count1_r4} from {len(hot_pool_r4)} hot, {count2_r4} from {len(cold_pool_r4)} cold). Skipping.")
    else:
        selected_r4 = set()
        import random # Ensure random is imported

        # Sample 3 from hot pool
        try:
            hot_picks = random.sample(hot_pool_r4, count1_r4)
            selected_r4.update(hot_picks)
        except ValueError:
            print(f"Warning: Could not sample {count1_r4} unique numbers from hot pool of size {len(hot_pool_r4)} for Row 4.")
            # Attempt to take as many as possible if sampling failed (e.g., pool too small unexpectedly)
            selected_r4.update(hot_pool_r4)


        # Sample 3 from cold pool, ensuring uniqueness from hot picks if possible
        # Create a list of cold candidates not already picked from the hot pool
        cold_candidates_for_sampling = [num for num in cold_pool_r4 if num not in selected_r4]
        needed_from_cold = count2_r4 # We aim for 3 cold numbers

        # How many can we actually pick from the unique cold candidates?
        can_pick_from_cold = min(needed_from_cold, len(cold_candidates_for_sampling))

        if can_pick_from_cold > 0:
            try:
                cold_picks = random.sample(cold_candidates_for_sampling, can_pick_from_cold)
                selected_r4.update(cold_picks)
            except ValueError:
                 # This shouldn't happen if can_pick_from_cold is calculated correctly, but handle defensively
                 print(f"Warning: Error sampling {can_pick_from_cold} from cold candidates for Row 4.")
        # else: No unique cold candidates available to pick from

        # Fill remaining slots randomly if needed (up to numbers_per_row)
        needed_fill = numbers_per_row - len(selected_r4)
        if needed_fill > 0:
            # print(f"Row 4: Need to fill {needed_fill} more numbers randomly.") # Optional debug print
            all_numbers = set(range(1, TOTAL_NUMBERS + 1))
            # Pool of numbers not yet selected
            remaining_pool = list(all_numbers - selected_r4)
            # How many can we actually fill?
            can_fill = min(needed_fill, len(remaining_pool))

            if can_fill > 0:
                try:
                    fill_picks = random.sample(remaining_pool, can_fill)
                    selected_r4.update(fill_picks)
                except ValueError:
                     print(f"Warning: Could not sample {can_fill} fill numbers for Row 4 from remaining pool of size {len(remaining_pool)}.")
                     # Row might be incomplete
            # else: No remaining numbers in the entire pool to pick from

        # Final check and append
        if len(selected_r4) == numbers_per_row:
            rows.append(sorted(list(selected_r4)))
            print("Generated Row 4 (Probabilistic Mix 3 Hot/3 Cold + Fill)")
        else:
            print(f"Warning: Could not generate Row 4 with exactly {numbers_per_row} unique numbers (got {len(selected_r4)}). Skipping row.")


    # --- Row 5: Mix Next Hot/Cold (e.g., Hot ranks 5-8 + Cold ranks 4-6) ---
    start_hot_r5 = count1_r4 # Start after the ones potentially used in Row 4 (this might need adjustment if pool_size_r4 is large)
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

    # --- Row 6: Random Sample from "Middle Ground" Numbers ---
    N_extremes = 15 # How many numbers to exclude from each end (hot, cold, least)
    exclusion_set = set(most_common_all[:N_extremes]) | \
                    set(least_common_all[:N_extremes]) | \
                    set(most_overdue_all[:N_extremes])

    all_possible_numbers = set(range(1, TOTAL_NUMBERS + 1))
    middle_pool = list(all_possible_numbers - exclusion_set)

    print(f"Row 6: Middle pool size (excluding top/bottom {N_extremes} hot/least/cold): {len(middle_pool)}")

    if len(middle_pool) >= numbers_per_row:
        try:
            row6 = random.sample(middle_pool, numbers_per_row)
            rows.append(sorted(row6))
            print("Generated Row 6 (Random Sample from Middle Ground)")
        except ValueError:
             print(f"Warning: Could not sample {numbers_per_row} from middle pool of size {len(middle_pool)}. Falling back.")
             # Fallback: Pure random sample
             row6 = random.sample(list(all_possible_numbers), numbers_per_row)
             rows.append(sorted(row6))
             print("Generated Row 6 (Pure Random Fallback)")

    else:
        print(f"Warning: Middle pool too small ({len(middle_pool)}). Falling back to pure random sample for Row 6.")
        # Fallback: Pure random sample
        try:
            row6 = random.sample(list(all_possible_numbers), numbers_per_row)
            rows.append(sorted(row6))
            print("Generated Row 6 (Pure Random Fallback)")
        except ValueError:
             print(f"Error: Cannot generate Row 6 even with fallback (not enough numbers overall?). Skipping.")


    # Deduplicate identical rows: replace any exact duplicates with the string "duplicate"
    seen = set()
    for idx, r in enumerate(rows):
        if isinstance(r, list):
            key = tuple(r)
            if key in seen:
                rows[idx] = "duplicate"
            else:
                seen.add(key)

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
        # Use a relative path for the fallback, assuming it's in the same directory structure
        fallback_file = 'Oz Lotto Statistics, Number Frequencies & Most Drawn.html'
        if os.path.exists(fallback_file):
             print(f"Attempting to use fallback file: {fallback_file}")
             latest_html_file = fallback_file
        else:
             # Try the absolute path provided before as a last resort
             abs_fallback_path = 'c:\\Users\\Owner\\Documents\\2025\\Lottery\\Oz Lotto Statistics, Number Frequencies & Most Drawn.html'
             if os.path.exists(abs_fallback_path):
                  print(f"Attempting to use absolute fallback file: {abs_fallback_path}")
                  latest_html_file = abs_fallback_path
             else:
                  print("Error: Fallback file not found. Exiting.")
                  exit()

    # 2. Read and parse the HTML
    try:
        with open(latest_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        print(f"Parsing data from: {os.path.basename(latest_html_file)}") # Use basename for cleaner output
    except Exception as e:
        print(f"Error reading or parsing HTML file {latest_html_file}: {e}")
        exit()

    # 3. Extract specific sections into a dictionary
    extracted_stats = {}

    # Hot Numbers (used for reference, main frequency from numerical)
    hot_numbers_table = find_table_after_heading(soup, "Hot Numbers (Most Common)")
    extracted_stats['hot'] = parse_table_data(hot_numbers_table, expected_cols=3)

    # Ordered by Ball Number (Primary source for frequency)
    extracted_stats['numerical'] = parse_numerical_order(soup)

    # Cold Numbers
    cold_numbers_table = find_table_after_heading(soup, "Cold Numbers (Most Overdue)")
    extracted_stats['cold'] = parse_table_data(cold_numbers_table, expected_cols=2)

    # Least Often Picked
    # Try finding the heading as h2 first, then div if needed
    least_often_heading = soup.find('h2', string=lambda t: t and "Least Often Picked Numbers" in t)
    if least_often_heading:
         least_often_table = find_table_after_heading(soup, "Least Often Picked Numbers", heading_tag='h2')
    else:
         least_often_table = find_table_after_heading(soup, "Least Often Picked Numbers", heading_tag='div') # Fallback to div search

    extracted_stats['least_often'] = parse_table_data(least_often_table, expected_cols=3)


    # Pairs/Triplets (Optional: print or use in advanced strategies)
    common_pairs_table = find_table_in_div_after_heading(soup, "Most Common Pairs")
    extracted_stats['pairs'] = parse_table_data(common_pairs_table, expected_cols=3)
    consec_pairs_table = find_table_in_div_after_heading(soup, "Most Common Consecutive Pairs")
    extracted_stats['consec_pairs'] = parse_table_data(consec_pairs_table, expected_cols=3)
    common_triplets_table = find_table_in_div_after_heading(soup, "Most Common Triplets")
    extracted_stats['triplets'] = parse_table_data(common_triplets_table, expected_cols=4)
    consec_triplets_table = find_table_in_div_after_heading(soup, "Most Common Consecutive Triplets")
    extracted_stats['consec_triplets'] = parse_table_data(consec_triplets_table, expected_cols=4)

    # Print extracted data summary (optional)
    print("\n--- Extracted Statistics Summary ---")
    print(f"Numerical Order entries found: {len(extracted_stats.get('numerical', []))}")
    print(f"Cold Numbers found: {len(extracted_stats.get('cold', []))}")
    print(f"Least Often Picked found: {len(extracted_stats.get('least_often', []))}")
    # Add more prints if desired


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
                    # Update Row 1 description
                    f.write("# Row 1: Probabilistic Weighted (Freq/Overdue Bias)\n")
                    f.write("# Row 2: Most Overdue (Top 7 Coldest) / Filled\n")
                    f.write("# Row 3: Next Most Common / Filled\n")
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