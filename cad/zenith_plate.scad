// Zenith Plate — parametric OpenSCAD model (mirrors breeze/cad.py)
// x = East, y = North, z = Up, metres. Open in OpenSCAD and use the Customizer.

/* [Site & programme] */
plot_x            = 72;    // E-W plate length
plot_y            = 48;    // N-S plate depth
plate_height      = 6.0;   // top of plate at edges
camber            = 0.04;  // rise / short span (CAE-7: <=0.06 costs <3 % emission)
enclosure_inset   = 6;
enclosure_height  = 4.2;

/* [Skin cell] */
cell_pitch        = 0.30;
accept_deg        = 85;    // CAE-3/6 optimum for selective emitter; 50-60 for broadband in humid sites
base_sheet        = 0.0015;
core              = 0.08;

/* [Structure] */
tile              = 3.0;
column_grid       = 12;
fork_drop         = 2.2;
beam_depth        = 0.28;
tank_volume       = 250;

/* [Display] */
show_cells_patch  = true;
patch             = 6;     // m, explicit cells at SE corner
mesh_n            = 24;    // plate surface resolution

rise = camber * min(plot_x, plot_y);
function pz(x, y) = plate_height + rise * (1 - pow(2*x/plot_x, 2)) * (1 - pow(2*y/plot_y, 2));

e_half = 0.5 * cell_pitch * sin(accept_deg);
cell_h = (0.5 * cell_pitch + e_half) / tan(accept_deg);
depth  = core + base_sheet + 0.0007;

// ---------------------------------------------------------------- plate
module plate() {
    nx = mesh_n; ny = round(mesh_n * plot_y / plot_x);
    pts = [for (k = [0:1]) for (i = [0:nx]) for (j = [0:ny])
             let(x = -plot_x/2 + i*plot_x/nx, y = -plot_y/2 + j*plot_y/ny)
             [x, y, pz(x, y) - k*depth]];
    id = function(k, i, j) k*(nx+1)*(ny+1) + i*(ny+1) + j;
    // triangulated, clockwise seen from outside (OpenSCAD convention)
    quads = concat(
        [for (i = [0:nx-1]) for (j = [0:ny-1]) [id(0,i,j), id(0,i,j+1), id(0,i+1,j+1), id(0,i+1,j)]],
        [for (i = [0:nx-1]) for (j = [0:ny-1]) [id(1,i,j), id(1,i+1,j), id(1,i+1,j+1), id(1,i,j+1)]],
        [for (i = [0:nx-1]) [id(0,i,0), id(0,i+1,0), id(1,i+1,0), id(1,i,0)]],
        [for (i = [0:nx-1]) [id(0,i+1,ny), id(0,i,ny), id(1,i,ny), id(1,i+1,ny)]],
        [for (j = [0:ny-1]) [id(0,0,j+1), id(0,0,j), id(1,0,j), id(1,0,j+1)]],
        [for (j = [0:ny-1]) [id(0,nx,j), id(0,nx,j+1), id(1,nx,j+1), id(1,nx,j)]]);
    faces = [for (q = quads) for (t = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]) t];
    color([0.80, 0.85, 0.92]) polyhedron(points = pts, faces = faces);
}

// ---------------------------------------------------------------- skin cell
module cell() {
    t = cell_pitch/2; e = e_half; h = cell_h;
    color([0.95, 0.95, 0.97]) difference() {
        polyhedron(points = [[-t,-t,0],[t,-t,0],[t,t,0],[-t,t,0],[-t,-t,h],[t,-t,h],[t,t,h],[-t,t,h]],
                   faces = [[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]);
        // cavity: inverted pyramid frustum
        polyhedron(points = [[-e,-e,0.0003],[e,-e,0.0003],[e,e,0.0003],[-e,e,0.0003],
                             [-t+0.0003,-t+0.0003,h+0.001],[t-0.0003,-t+0.0003,h+0.001],[t-0.0003,t-0.0003,h+0.001],[-t+0.0003,t-0.0003,h+0.001]],
                   faces = [[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]);
    }
    color([0.15, 0.25, 0.55]) translate([-e, -e, 0]) cube([2*e, 2*e, 0.0004]); // selective emitter
}

// ---------------------------------------------------------------- structure
module strut(a, b, r) { hull() { translate(a) sphere(r, $fn=10); translate(b) sphere(r, $fn=10); } }

module structure() {
    g = column_grid; h = g/2;
    color([0.54, 0.43, 0.29]) {
        for (x = [-plot_x/2 + g/4 : h : plot_x/2])
            for (y = [-plot_y/2 : plot_y/16 : plot_y/2 - plot_y/16])
                hull() for (yy = [y, y + plot_y/16]) translate([x, yy, pz(x, yy) - depth - beam_depth]) cube([0.2, 0.01, beam_depth], center = false);
        for (y = [-plot_y/2 + g/4 : h : plot_y/2])
            for (x = [-plot_x/2 : plot_x/24 : plot_x/2 - plot_x/24])
                hull() for (xx = [x, x + plot_x/24]) translate([xx, y, pz(xx, y) - depth - beam_depth]) cube([0.01, 0.2, beam_depth]);
    }
    color([0.36, 0.42, 0.48])
    for (x = [-plot_x/2 + g/2 : g : plot_x/2]) for (y = [-plot_y/2 + g/2 : g : plot_y/2]) {
        zb = min([for (dx = [-1, 1]) for (dy = [-1, 1]) pz(x + dx*g/4, y + dy*g/4)]) - depth - beam_depth;
        fork = zb - fork_drop;
        translate([x, y, 0]) cylinder(r = 0.137, h = fork, $fn = 24);
        for (dx = [-1, 1]) for (dy = [-1, 1])
            strut([x, y, fork], [x + dx*g/4, y + dy*g/4, pz(x + dx*g/4, y + dy*g/4) - depth - beam_depth], 0.084);
    }
}

module enclosure() {
    color([0.88, 0.89, 0.91])
    translate([-plot_x/2 + enclosure_inset, -plot_y/2 + enclosure_inset, 0])
        cube([plot_x - 2*enclosure_inset, plot_y - 2*enclosure_inset, enclosure_height]);
}

module tank() {
    r = sqrt(tank_volume / (PI * 5));
    color([0.36, 0.56, 0.85]) translate([0, 0, -6]) cylinder(r = r, h = 5, $fn = 64);
}

plate(); structure(); enclosure(); tank();
if (show_cells_patch) {
    n = floor(patch / cell_pitch);
    for (a = [0:n-1]) for (b = [0:n-1]) {
        cx = plot_x/2 - (a + 0.5)*cell_pitch; cy = -plot_y/2 + (b + 0.5)*cell_pitch;
        translate([cx, cy, pz(cx, cy) + 0.002]) cell();
    }
}
echo(str("cell height = ", cell_h*1000, " mm; emitter fraction = ", pow(2*e_half/cell_pitch, 2), "; rise = ", rise, " m"));
