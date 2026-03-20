import argparse
import re


def extract_numbers(text):
    float_list = []
    odd_list = []
    even_list = []

    tokens = re.findall(r'\d+\.\d+|\d+', text)

    for token in tokens:
        if '.' in token:
            float_list.append(float(token))
        elif int(token) % 2 != 0:
            odd_list.append(int(token))
        else:
            even_list.append(int(token))

    return float_list, odd_list, even_list


def main():
    parser = argparse.ArgumentParser(description="Extract numbers from a string.")
    parser.add_argument("--text", type=str, required=True, help="Input string")
    args = parser.parse_args()

    float_list, odd_list, even_list = extract_numbers(args.text)

    print(f"Float list: {float_list}")
    print(f"Odd list:   {odd_list}")
    print(f"Even list:  {even_list}")


if __name__ == "__main__":
    main()