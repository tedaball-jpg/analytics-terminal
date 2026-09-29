def main():
    principal = float(input("Enter the principal amount: "))
    rate = float(input("Enter the annual interest rate (%): "))
    years = int(input("Enter the number of years: "))

    value = principal
    print(f"\nYear 0: {value:.2f}")
    for year in range(1, years + 1):
        value *= 1 + rate / 100
        print(f"Year {year}: {value:.2f}")


if __name__ == "__main__":
    main()
