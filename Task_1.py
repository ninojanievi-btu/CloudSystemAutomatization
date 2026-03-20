import argparse

myList = []

def armstrong_list(x, y):
    while x <= y:
        my_str = str(x)
        my_sum = 0
        for i in my_str:
            my_sum = my_sum + (int(i) ** len(my_str))
        if my_sum == x:
            myList.append(x)
        x = x + 1
    return myList


def recursive_sum(armstr_list):
    if not armstr_list:
        return 0
    return armstr_list[0] + recursive_sum(armstr_list[1:])


def main():
    parser = argparse.ArgumentParser(description="Find Armstrong numbers in a range.")
    parser.add_argument("--start", type=int, default=9, help="Range start")
    parser.add_argument("--end", type=int, default=9999, help="Range end")
    args = parser.parse_args()

    numbers = armstrong_list(args.start, args.end)
    total = recursive_sum(numbers)

    print("Armstrong numbers:")
    for num in numbers:
        print(num)
    print(f"\nSum: {total}")


if __name__ == "__main__":
    main()