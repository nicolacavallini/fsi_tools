Point(1) = {-3,-1,0};
Point(2) = {-3,1,0};
Point(3) = {1,-1,0};
Point(4) = {1,1,0};

Point(6) = {-2,-0.11,0};
Point(7) = {-1.8,-0.11,0};
Point(8) = {-1.8,0.09,0};
Point(9) = {-2,0.09,0};
Line(1) = {1,3};
Line(2) = {3,4};
Line(3) = {4,2};
Line(4) = {2,1};
Line(5) = {6,7};
Line(6) = {7,8};
Line(7) = {8,9};
Line(8) = {9,6};
//Circle(5) = {6,5,7};
//Circle(6) = {7,5,8};
//Circle(7) = {8,5,9};
//Circle(8) = {9,5,6};
Line Loop(9) = {1,2,3,4}; // exterior loop
Line Loop(10) = {5,6,7,8};
//Plane Surface(1) = {9}; // interior surface
Plane Surface(2) = {9,10}; // exterior surface (with a whole)
