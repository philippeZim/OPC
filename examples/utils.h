#ifndef UTILS_H
#define UTILS_H

#ifndef OPC_STRUCT_Point
#define OPC_STRUCT_Point
typedef struct Point {
    float x;
    float y;
} Point;
#endif

Point create_point(float x, float y);

#endif // UTILS_H