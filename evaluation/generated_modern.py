import sys
import re

def c_atoi(s: str) -> int:
    m = re.match(r'^\s*([+-]?\d+)', s)
    return int(m.group(1)) if m else 0

def c_atof(s: str) -> float:
    m = re.match(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)', s)
    return float(m.group(1)) if m else 0.0

def main():
    for raw_line in sys.stdin:
        line = re.split(r'[\r\n]', raw_line)[0]
        if len(line) < 22:
            print("ERR_MALFORMED_RECORD")
            continue

        acct = line[0:6]
        year_s = line[6:10]
        days_s = line[10:13]
        amt_s = line[13:22]

        year = c_atoi(year_s)
        days_late = c_atoi(days_s)
        amount = c_atof(amt_s)

        if amount < 0.0:
            print(f"{acct}|ERR_NEGATIVE_AMT")
            continue

        days_in_year = 366 if ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)) else 365
        fee_paise = int((amount * 0.05 * days_late / days_in_year) * 100.0)
        total = amount + (fee_paise / 100.0)

        print(f"{acct}|YR:{year}|DAYS:{days_late}|TOTAL:{total:.2f}")

if __name__ == "__main__":
    main()
