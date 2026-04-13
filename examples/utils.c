#ifndef OPC_STRUCT_Point
#define OPC_STRUCT_Point
typedef struct Point {
    float x;
    float y;

} Point;
#endif // OPC_STRUCT_Point
Point create_point(float x, float y) {
    Point p;
    p.x = x;
    p.y = y;
    return p;
}