import sys

def main():
    for line in sys.stdin:
        line = line.split('\r')[0].split('\n')[0]
        if len(line) < 22:
            print("ERR_MALFORMED_RECORD")
            continue

        acct = line[0:6]
        year_s = line[6:10]
        days_s = line[10:13]
        amt_s = line[13:22]

        year = int(year_s)
        days_late = int(days_s)
        amount = float(amt_s)

        if amount < 0.0:
            print(f"{acct}|ERR_NEGATIVE_AMT")
            continue

        days_in_year = 366 if ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)) else 365
        fee_paise = int((amount * 0.05 * days_late / days_in_year) * 100.0)
        total = amount + (fee_paise / 100.0)

        print(f"{acct}|YR:{year}|DAYS:{days_late}|TOTAL:{total:.2f}")

if __name__ == "__main__":
    main()