#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

char * read_file(const char *file_name) {
    FILE * fp;
    long lSize;
    char * buffer;

    fp = fopen(file_name, "rb");
    if (!fp) {
        perror(file_name);
        exit(1);

    }
    fseek(fp, 0L, SEEK_END);
    lSize = ftell(fp);
    rewind(fp);

    buffer = calloc(1, lSize+1);
    if (!buffer) {
        fclose(fp);
        fputs("memory alloc fails",stderr);
        exit(1);

    }
    if (1 != fread(buffer, lSize, 1, fp)) {
        fclose(fp);
        free(buffer);
        fputs("entire read fails", stderr);
        exit(1);

    }
    fclose(fp);
    return buffer;

}
int main(void) {
    char * text = read_file("input.txt");

    uint32_t result_part_1 = 0;
    uint32_t result_part_2 = 0;
    uint32_t dial = 50;
    int end = 0;
    size_t i = 0;
    while (1) {
        if (text[i] == '\0' || end) {
            break;
        }
        char save_direction = text[i++];
        uint32_t parsed_number = 0;
        while (text[i] != '\n' && text[i] != '\0') {
            parsed_number *= 10;
            parsed_number += text[i++] - '0';

        }
        if (text[i++] == '\0') {
            end = 1;

        }
        result_part_2 += parsed_number / 100;
        parsed_number %= 100;
        if (save_direction == 'R') {
            if (dial + parsed_number > 100) {
                result_part_2 += 1;

            }
            dial = (dial + parsed_number) % 100;
        } else {
            if (dial != 0 && parsed_number > dial) {
                result_part_2 += 1;
            }
            int32_t change = (int32_t)dial - (int32_t)parsed_number;
            if (change < 0) {
                dial = 100 + change;
            } else {
                dial = change % 100;

            }
        }
        if (dial == 0) {
            result_part_1++;
            result_part_2++;

        }
    }
    printf("Result Part 1: %d\n", result_part_1);
    printf("Result Part 2: %d\n", result_part_2);
    return 0;
}