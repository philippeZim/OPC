#include <stdio.h>

#include "utils.h"

int main() {
    Point p = create_point(5.0, 10.0);
    printf("Point: %f, %f", p.x, p.y);
    return 0;
}