""" graph geometry library

For generating heuristic coordinates and z-matrices from graphs
"""
import numpy
import scipy.optimize
from qcelemental import constants as qcc
from qcelemental import periodictable as pt
import automol.zmat
from automol.graph._res import resonance_dominant_atom_hybridizations
from automol.graph._ring import ring_systems_decomposed_atom_keys
from automol.graph._graph import atom_neighbor_keys
from automol.graph._graph import atom_symbols
from automol.graph._graph import longest_chain


# bond distances
XY_DIST = 1.5       # angstroms
XH_DIST = 1.1       # angstroms

# bond angles
TET_ANG = 109.4712  # degrees
TRI_ANG = 120.      # degrees
LIN_ANG = 180.      # degrees

# dihedral angles
CIS_DIH = 0.        # degrees
TRA_DIH = 180.      # degrees

# miscellaneous
RIT_ANG = 90.       # degrees


def heuristic_bond_distance(gra, key1, key2, check=True):
    """ heuristic bond distance
    """
    if check:
        assert key1 in atom_neighbor_keys(gra)[key2]

    sym_dct = atom_symbols(gra)
    sym1 = sym_dct[key1]
    sym2 = sym_dct[key2]

    if pt.to_Z(sym1) == 1 or pt.to_Z(sym2) == 1:
        dist = XH_DIST
    else:
        dist = XY_DIST

    return dist


def heuristic_bond_angle(gra, key1, key2, key3, check=True):
    """ heuristic bond angle
    """
    if check:
        assert {key1, key3} <= set(atom_neighbor_keys(gra)[key2])

    hyb_dct = resonance_dominant_atom_hybridizations(gra)
    hyb2 = hyb_dct[key2]
    if hyb2 == 3:
        ang = TET_ANG
    elif hyb2 == 2:
        ang = TRI_ANG
    else:
        assert hyb2 == 1
        ang = LIN_ANG

    return ang


def ring_arc_bond_angle(num, end_dist=XY_DIST, bond_dist=XY_DIST):
    """ find the bond angle (in degrees) for completing a circular arc between
    points

    We will form an arc of n atoms such that the ends are a distance r_e
    apart and each pair of neighboring atoms is a distance r_b apart.
    Let the total angle subtended by the arc be theta and let the circle
    radius be R.
    Furthermore, let the arc angle subtended between two neighboring atoms be
    alpha, so that
        alpha = theta/(n-1)
    Let us consider two isosceles triangles: the one formed by two neighboring
    atoms on the arc with the circle center (triangle N), and the one formed by
    the arc ends with the circle center (triangle E).

    By bisecting triangle N, we find that
        sin(alpha/2) = (r_b/2)/R = r_b/(2*R)
    By bisecting triangle E, we find that
        +-sin(theta/2) = (r_e/2)/R = r_e/(2*R)
    where the sign flips when theta > pi.
    Dividing these two equations gives us.
        sin(alpha/2)/sin(theta/2) = r_b/r_e
    By substituting in the expression for alpha in terms of theta, we can solve
    for theta by finding the first positive root of the following equation.
        sin(theta/(2*(n-1)))/sin(theta/2) - r_b/r_e = 0
    Note that, in solving this equation numerically, we must avoid the
    singularity at theta = 0.

    Once we know theta, we can find the bond angle for atoms along the arc as
    follows.
    Let beta be the base angle of the triangle N, and note that alpha is the
    vertex angle.
    Geometrically, then, beta is the bisection of the bond angle, and therefore
    the bond angle is
        bond_angle = 2*beta.
    Furthermore, by the angle sum formula for triangle N, we have that
        alpha + 2*beta = 180 degrees (pi radians)
    It therefore follows that
        bond_angle = 180 - alpha = 180 - theta/(n-1)
    """

    def _f(theta):
        if numpy.abs(theta) < 0.001:
            theta = 0.001

        rhs = numpy.sin(theta/(2*(num-1)))/numpy.sin(theta/2)
        lhs = bond_dist / end_dist
        return rhs - lhs

    # if the end distance is longer than the sum of the bond distances, set the
    # angle to 180; otherwise solve for the correct bond angle to complete the
    # arc, as described above
    if end_dist > (num - 1) * bond_dist:
        ang = 180.
    else:
        res_obj = scipy.optimize.root_scalar(_f, method='brentq',
                                             bracket=[0.01, 2*numpy.pi])

        assert res_obj.converged
        # convert from radians to degrees
        theta = res_obj.root * qcc.conversion_factor('radian', 'degree')

        ang = 180. - theta/(num-1)

    return ang


def chain_zmatrix(gra, chain_keys):
    """ z-matrix for a chain of heavy atoms
    """
    chain_iter = iter(chain_keys)

    sym_dct = atom_symbols(gra)     # graph keys -> atomic symbols
    row_dct = {}                    # graph keys -> z-matrix rows
    zma = ()                        # empty z-matrix

    key3 = row3 = r34 = None
    key2 = row2 = a234 = None
    key1 = row1 = d1234 = None

    for key4 in chain_iter:
        row_dct[key4] = automol.zmat.count(zma)

        if key3 is not None:
            row3 = row_dct[key3]
            r34 = heuristic_bond_distance(gra, key3, key4)

        if key2 is not None:
            row2 = row_dct[key2]
            a234 = heuristic_bond_angle(gra, key2, key3, key4)

        if key1 is not None:
            row1 = row_dct[key1]
            d1234 = TRA_DIH

        zma = automol.zmat.add_atom(zma, sym_dct[key4],
                                    key_row=[row3, row2, row1],
                                    val_row=[r34, a234, d1234])

        # now, shift the keys for the next one up
        key1, key2, key3 = key2, key3, key4

    chain_rows = tuple(map(row_dct.__getitem__, chain_keys))
    return zma, chain_rows


def ring_system_zmatrix(gra, ring_system_decomp_keys):
    """ z-matrix for a ring system

    :param gra: the graph
    :param ring_system_decomp_keys: keys for the ring system, decomposed into a
        single ring with several arcs extending from it; the end atoms for each
        next arc must be contained in the preceding parts of the system
    """
    ring_sys_iter = iter(ring_system_decomp_keys)

    ring_keys = next(ring_sys_iter)
    print(automol.graph.string(gra))
    print(ring_keys)

    zma, ring_rows = ring_zmatrix(gra, ring_keys)
    row_dct = dict(zip(ring_keys, ring_rows))

    arc_keys = next(ring_sys_iter)
    end_keys = (arc_keys[0], arc_keys[-1])
    end_rows = list(map(row_dct.__getitem__, end_keys))
    end_dist = automol.zmat.distance(zma, *end_rows, angstrom=True)
    print(end_keys)
    print(end_dist)
    arc_zma, arc_rows = ring_zmatrix(gra, arc_keys, end_dist=end_dist)
    # arc_row_dct = dict(zip(arc_keys, arc_rows))

    ang1 = automol.zmat.central_angle(
        arc_zma, arc_rows[1], arc_rows[0], arc_rows[-1], degree=True)
    dih1 = 90.
    dih2 = 0.

    key3 = end_keys[0]
    key2 = end_keys[1]
    row3 = ring_keys.index(key3)
    row2 = ring_keys.index(key2)
    row1 = row2 - 1 if row2 > 0 else row2 + 1
    row_mat = [[row2, row1], [row2]]
    val_mat = [[ang1, dih1], [dih2]]
    zma = automol.zmat.join_replace_one(zma, arc_zma, row3, row_mat, val_mat)

    geo = automol.zmat.geometry(zma)
    print(automol.zmat.string(zma))
    print(automol.geom.string(geo))


def ring_zmatrix(gra, ring_keys, bond_dist=XY_DIST, end_dist=XY_DIST):
    """ z-matrix for a ring (or arc) of heavy atoms

    :param bond_dist: bond distances between neighboring atoms in the ring
    :type bond_dist: float
    :param end_dist: if this is an arc connecting two points of a larger ring,
        this sets the distance between the arc ends
    :type end_dist: float
    """
    num = len(ring_keys)
    bond_ang = ring_arc_bond_angle(num, end_dist=end_dist, bond_dist=bond_dist)

    ring_iter = iter(ring_keys)

    sym_dct = atom_symbols(gra)
    row_dct = {}
    zma = ()

    key3 = row3 = None
    key2 = row2 = None
    key1 = row1 = None

    r34 = bond_dist
    a234 = bond_ang
    d1234 = 0.

    for key4 in ring_iter:
        row_dct[key4] = automol.zmat.count(zma)

        if key3 is not None:
            row3 = row_dct[key3]

        if key2 is not None:
            row2 = row_dct[key2]

        if key1 is not None:
            row1 = row_dct[key1]

        zma = automol.zmat.add_atom(zma, sym_dct[key4],
                                    key_row=[row3, row2, row1],
                                    val_row=[r34, a234, d1234])

        # now, shift the keys for the next one up
        key1, key2, key3 = key2, key3, key4

    ring_rows = tuple(map(row_dct.__getitem__, ring_keys))
    return zma, ring_rows


if __name__ == '__main__':
    import automol

    # chain
    ICH = automol.smiles.inchi('CCCCCC')
    GRA = automol.inchi.graph(ICH)
    # print(automol.graph.string(GRA, one_indexed=False))
    CHAIN_KEYS = longest_chain(GRA)
    print(CHAIN_KEYS)
    # ZMA, CHAIN_ROWS = chain_zmatrix(GRA, CHAIN_KEYS)

    # print(CHAIN_ROWS)
    # print(automol.zmat.string(ZMA))
    # GEO = automol.zmat.geometry(ZMA)
    # print(automol.geom.string(GEO))

    # ring
    # ICH = automol.smiles.inchi('C12CC(C2)CC1')
    ICH = automol.smiles.inchi('C1CCC2CC(CCC3C4CCC5CC4C53)CC2C1')
    GRA = automol.inchi.graph(ICH)

    DECOMPS = ring_systems_decomposed_atom_keys(GRA)
    ring_system_zmatrix(GRA, DECOMPS[0])

    # RING_SYSTEMS = ring_systems(GRA)

    # RING_SYSTEM1 = RING_SYSTEMS[1]

    # decompose_ring_system_atom_keys(RING_SYSTEM1)

    # RINGS1 = rings(RING_SYSTEM1)
    # print(len(RINGS1))

    # print(bridgehead_atom_keys(RINGS1[0], RINGS1[1]))
    # print(bridgehead_atom_keys(RINGS1[0], RINGS1[2]))
    # print(bridgehead_atom_keys(RINGS1[1], RINGS1[2]))

    # print(automol.graph.string(GRA, one_indexed=False))
    # RING_KEYS_LST = sorted(rings_atom_keys(GRA), key=len)
    # RING1_KEYS = RING_KEYS_LST[0]
    # RING2_KEYS = RING_KEYS_LST[1]
    # ZMA1, RING1_ROWS = ring_zmatrix(GRA, RING_KEYS_LST[0])
    # ZMA2, RING2_ROWS = ring_zmatrix(GRA, RING_KEYS_LST[1])

    # print(set(RING1_KEYS) & set(RING2_KEYS))
    # # print(RING1_ROWS)
    # # print(RING2_ROWS)
    # # print(automol.zmat.string(ZMA1))
    # # print(automol.zmat.string(ZMA2))
    # # GEO1 = automol.zmat.geometry(ZMA1)
    # # GEO2 = automol.zmat.geometry(ZMA2)
    # # print(automol.geom.string(GEO1))
    # # print()
    # # print(automol.geom.string(GEO2))
