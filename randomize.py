import re
import random
import string

def randomize_email_template(template):
    """
    Process an email template and replace all random tags with random strings.

    Tags format:
    - Unique tags: [ua_size], [ual_size], [uau_size], [uan_size], [uanl_size], [uanu_size], [un_size], [uhu_size], [uhl_size]
    - Random tags: [a_size], [al_size], [au_size], [an_size], [anl_size], [anu_size], [n_size], [hu_size], [hl_size]

    Size can be a fixed number (e.g., _12) or a range (e.g., _5_15)

    Behavior:
    - Unique tags (starting with 'u') will have unique values across the template
    - Non-unique tags with the same pattern (e.g., all [a_5] tags) will have the same value throughout the template

    Returns:
    - The processed template with all tags replaced by random strings
    - A dictionary of unique values used (for reference)
    """
    # Define character sets
    alpha = string.ascii_letters
    alpha_lower = string.ascii_lowercase
    alpha_upper = string.ascii_uppercase
    numeric = string.digits
    hex_upper = string.digits + 'ABCDEF'
    hex_lower = string.digits + 'abcdef'

    alphanumeric = alpha + numeric
    alphanumeric_lower = alpha_lower + numeric
    alphanumeric_upper = alpha_upper + numeric

    # Store unique values to ensure no duplicates for unique tags
    unique_values = {}

    # Store values for non-unique tags to ensure consistency
    consistent_values = {}

    # Define tag patterns
    # Format: [tag_size] or [tag_min_max]
    tag_pattern = r'\[(ua|ual|uau|uan|uanl|uanu|un|uhu|uhl|a|al|au|an|anl|anu|n|hu|hl)(?:_(\d+)(?:_(\d+))?)?\]'

    def get_random_string(charset, size):
        """Generate a random string of specified size from the given charset."""
        if isinstance(size, tuple):
            min_size, max_size = size
            actual_size = random.randint(min_size, max_size)
        else:
            actual_size = size
        return ''.join(random.choice(charset) for _ in range(actual_size))

    def get_unique_random_string(tag_type, charset, size):
        """Generate a unique random string, ensuring no duplicates for the tag type."""
        if tag_type not in unique_values:
            unique_values[tag_type] = set()

        # Try to generate a unique value (with a reasonable limit to prevent infinite loops)
        for _ in range(1000):
            value = get_random_string(charset, size)
            if value not in unique_values[tag_type]:
                unique_values[tag_type].add(value)
                return value

        # If we can't find a unique value after many attempts, append a random suffix
        # This is a fallback to prevent infinite loops
        base_value = get_random_string(charset, size)
        unique_value = f"{base_value}_{random.randint(1000, 9999)}"
        unique_values[tag_type].add(unique_value)
        return unique_value

    def replace_match(match):
        tag_type = match.group(1)
        size1 = match.group(2)
        size2 = match.group(3)

        # Determine size (fixed or range)
        if size2:
            size = (int(size1), int(size2))
        elif size1:
            size = int(size1)
        else:
            # Default size if not specified
            size = 8

        # Handle different tag types
        is_unique = tag_type.startswith('u')

        # Remove the 'u' prefix for unique tags to get the base tag type
        base_tag_type = tag_type[1:] if is_unique else tag_type

        # Select the character set based on the tag type
        if base_tag_type == 'a':
            charset = alpha
        elif base_tag_type == 'al':
            charset = alpha_lower
        elif base_tag_type == 'au':
            charset = alpha_upper
        elif base_tag_type == 'an':
            charset = alphanumeric
        elif base_tag_type == 'anl':
            charset = alphanumeric_lower
        elif base_tag_type == 'anu':
            charset = alphanumeric_upper
        elif base_tag_type == 'n':
            charset = numeric
        elif base_tag_type == 'hu':
            charset = hex_upper
        elif base_tag_type == 'hl':
            charset = hex_lower
        else:
            # Fallback for unknown tags
            return match.group(0)

        # Generate random string (unique or not)
        if is_unique:
            return get_unique_random_string(tag_type, charset, size)
        else:
            # For non-unique tags, create a key based on the tag pattern
            # This ensures all instances of the same tag pattern get the same value
            tag_key = f"{tag_type}_{size1 or '8'}{f'_{size2}' if size2 else ''}"

            # If we've already generated a value for this tag pattern, reuse it
            if tag_key in consistent_values:
                return consistent_values[tag_key]

            # Otherwise, generate a new value and store it for future use
            value = get_random_string(charset, size)
            consistent_values[tag_key] = value
            return value

    # Process the template by replacing all matching tags
    result = re.sub(tag_pattern, replace_match, template)

    # Combine unique and consistent values for the return value
    all_values = {
        'unique': unique_values,
        'consistent': consistent_values
    }

    return result, all_values

# Example usage
if __name__ == "__main__":
    # Example template
    email_template = """
    Hello [uan_8],

    Your verification code is [n_6]. This code will expire in 10 minutes.

    Your unique identifier is [uan_4_8] and your backup code is [uhl_12].

    For record keeping, here's a random reference: [anl_10]

    Best regards,
    The [a_5_10] Team
    """

    randomized_template, all_values = randomize_email_template(email_template)
    print("Randomized Template:")
    print(randomized_template)

    print("\nUnique Values Used:")
    for tag_type, values in all_values['unique'].items():
        print(f"{tag_type}: {values}")

    print("\nConsistent Values Used:")
    for tag_pattern, value in all_values['consistent'].items():
        print(f"{tag_pattern}: {value}")