#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Legacy Batch Late-Fee & Interest Processor
// Input format (fixed-width): ACCT(6) YEAR(4) DAYS(3) AMOUNT(9)
int main() {
    char line[64];
    while (fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = 0;
        if (strlen(line) < 22) {
            printf("ERR_MALFORMED_RECORD\n");
            continue;
        }

        char acct[7], year_s[5], days_s[4], amt_s[10];
        strncpy(acct, line, 6); acct[6] = '\0';
        strncpy(year_s, line + 6, 4); year_s[4] = '\0';
        strncpy(days_s, line + 10, 3); days_s[3] = '\0';
        strncpy(amt_s, line + 13, 9); amt_s[9] = '\0';

        int year = atoi(year_s);
        int days_late = atoi(days_s);
        double amount = atof(amt_s);

        if (amount < 0.0) {
            printf("%s|ERR_NEGATIVE_AMT\n", acct);
            continue;
        }

        int days_in_year = ((year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)) ? 366 : 365;
        // Legacy rule: truncate daily penalty to integer paise before adding
        int fee_paise = (int)((amount * 0.05 * days_late / days_in_year) * 100.0);
        double total = amount + (fee_paise / 100.0);

        printf("%s|YR:%d|DAYS:%d|TOTAL:%.2f\n", acct, year, days_late, total);
    }
    return 0;
}
