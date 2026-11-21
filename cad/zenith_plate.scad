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
cell_type         = "ribs"; // ["ribs", "funnel"] round 2 = vertical ribs holding the film over still air
cell_pitch        = 0.30;
rib_height        = 0.10;  // CAE-8: still-air gap 75-100 mm (stably stratified under a cold emitter)
accept_deg        = 85;    // funnel variant only (round 1; 50-60 for broadband in humid sites)
wall_sheet        = 0.0003;
base_sheet        = 0.0015;
core              = 0.08;

/* [Round 2: subterranean programme, pit, airflow] */
sunk_storeys      = 3;     // 0 = round-1 exposed storey at grade
storey_height     = 4.5;
vault_rise        = 1.8;
vault_cover       = 0.6;   // earth over 150 mm PIR
pit_volume        = 6000;  // seasonal stratified water pit (CAE-10/11)
pit_depth         = 6;
stacks            = 4;
stack_diameter    = 2.4;
stack_above_plate = 3;
lightwells        = 2;
lightwell_size    = 8;
earth_tubes       = 8;

/* [Structure] */
tile              = 3.0;
column_grid       = 12;
fork_drop         = 2.2;
beam_depth        = 0.28;
tank_volume       = 0;     // round 1 used a 250 m3 diurnal tank; round 2 the pit does both

/* [Display] */
show_cells_patch  = true;
patch             = 6;     // m, explicit cells at SE corner
mesh_n            = 24;    // plate surface resolution

rise = camber * min(plot_x, plot_y);
function pz(x, y) = plate_height + rise * (1 - pow(2*x/plot_x, 2)) * (1 - pow(2*y/plot_y, 2));

e_half = cell_type == "ribs" ? 0.5 * cell_pitch - wall_sheet/2 : 0.5 * cell_pitch * sin(accept_deg);
cell_h = cell_type == "ribs" ? rib_height : (0.5 * cell_pitch + e_half) / tan(accept_deg);
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
    if (cell_type == "ribs") rib_cell(); else funnel_cell();
}

module rib_cell() {
    t = cell_pitch/2; h = cell_h; w = wall_sheet;
    color([0.95, 0.95, 0.97]) difference() {
        translate([-t, -t, 0]) cube([2*t, 2*t, h]);
        translate([-t + w/2, -t + w/2, -0.001]) cube([2*t - w, 2*t - w, h + 0.002]);
    }
    color([0.15, 0.25, 0.55]) translate([-t + w/2, -t + w/2, 0]) cube([2*t - w, 2*t - w, 0.0004]);
    color([1, 1, 1, 0.25]) translate([-t, -t, h]) cube([2*t, 2*t, 0.0002]);   // 12 um LDPE film
}

module funnel_cell() {
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

ex = plot_x/2 - enclosure_inset; ey = plot_y/2 - enclosure_inset;
zb = -sunk_storeys * storey_height;

module enclosure() {
    if (sunk_storeys == 0) {
        color([0.88, 0.89, 0.91]) translate([-ex, -ey, 0]) cube([2*ex, 2*ey, enclosure_height]);
    } else {
        color([0.80, 0.76, 0.70]) translate([-ex, -ey, zb]) cube([2*ex, 2*ey, -zb]);          // sunk programme
        color([0.55, 0.45, 0.35]) intersection() {                                            // earth-covered barrel vault
            translate([-ex, -ey, 0]) cube([2*ex, 2*ey, vault_rise + vault_cover]);
            scale([1, 1, (vault_rise + vault_cover) / ey]) rotate([0, 90, 0]) cylinder(r = ey, h = 2*ex, center = true, $fn = 64);
        }
        pa = pit_volume / pit_depth; sy = min(2*ey, sqrt(pa * ey / ex)); sx = pa / sy;
        color([0.2, 0.45, 0.8, 0.8]) translate([-sx/2, -sy/2, zb - pit_depth]) cube([sx, sy, pit_depth - 0.4]);   // seasonal pit
        for (k = [0 : lightwells - 1]) {
            cx = (-1 + 2*(k + 0.5)/lightwells) * ex * 0.6;
            color([0.8, 0.9, 0.95, 0.5]) translate([cx - lightwell_size/2, -lightwell_size/2, zb + storey_height])
                cube([lightwell_size, lightwell_size, -zb - storey_height + vault_rise + vault_cover + 0.3]);
        }
        for (k = [0 : stacks - 1]) {
            cx = (-1 + 2*(k % 2 + 0.5)/2) * ex * 0.55;
            cy = stacks > 2 ? (-1 + 2*(floor(k/2) + 0.5)/2) * ey * 0.5 : 0;
            color([0.6, 0.62, 0.66]) translate([cx, cy, 0]) cylinder(r = stack_diameter/2, h = pz(cx, cy) + stack_above_plate, $fn = 32);
        }
        for (k = [0 : earth_tubes - 1]) {
            a = 360 * (k + 0.5) / earth_tubes;
            px = 0.48 * plot_x * cos(a); py = 0.48 * plot_y * sin(a);
            color([0.45, 0.45, 0.45]) {
                translate([px, py, -3]) cylinder(r = 0.25, h = 4.5, $fn = 12);
                hull() { translate([px, py, -3]) sphere(0.2, $fn = 8); translate([0.9*max(-ex, min(ex, px)), 0.9*max(-ey, min(ey, py)), -3]) sphere(0.2, $fn = 8); }
            }
        }
    }
}

module tank() {
    if (tank_volume > 0) tank_body();
}
module tank_body() {
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
echo(str("cell height = ", cell_h*1000, " mm; emitter fraction = ", pow(2*e_half/cell_pitch, 2), "; rise = ", rise, " m; floor area = ",
          4*ex*ey*max(1, sunk_storeys), " m2; pit capacity = ", pit_volume*4186*8/3.6e6, " MWh (8 K)"));
