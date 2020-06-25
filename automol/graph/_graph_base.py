""" base molecular graph library
"""
import yaml
from automol import dict_
import automol.create.graph as _create
import automol.dict_.multi as mdict

ATM_PROP_NAMES = ('symbol', 'implicit_hydrogen_valence', 'stereo_parity')
BND_PROP_NAMES = ('order', 'stereo_parity')

ATM_SYM_POS = 0
ATM_IMP_HYD_VLC_POS = 1
ATM_STE_PAR_POS = 2

BND_ORD_POS = 0
BND_STE_PAR_POS = 1


# getters
def atoms(xgr):
    """ atoms, as a dictionary
    """
    atm_dct, _ = xgr
    return atm_dct


def bonds(xgr):
    """ bonds, as a dictionary
    """
    _, bnd_dct = xgr
    return bnd_dct


def atom_keys(xgr):
    """ atom keys
    """
    return frozenset(atoms(xgr).keys())


def bond_keys(xgr):
    """ bond keys
    """
    return frozenset(bonds(xgr).keys())


def atom_symbols(xgr):
    """ atom symbols, as a dictionary
    """
    return mdict.by_key_by_position(atoms(xgr), atom_keys(xgr), ATM_SYM_POS)


def atom_implicit_hydrogen_valences(xgr):
    """ atom implicit hydrogen valences, as a dictionary
    """
    return mdict.by_key_by_position(atoms(xgr), atom_keys(xgr),
                                    ATM_IMP_HYD_VLC_POS)


def atom_stereo_parities(sgr):
    """ atom parities, as a dictionary
    """
    return mdict.by_key_by_position(atoms(sgr), atom_keys(sgr),
                                    ATM_STE_PAR_POS)


def bond_orders(rgr):
    """ bond orders, as a dictionary
    """
    return mdict.by_key_by_position(bonds(rgr), bond_keys(rgr), BND_ORD_POS)


def bond_stereo_parities(sgr):
    """ bond parities, as a dictionary
    """
    return mdict.by_key_by_position(bonds(sgr), bond_keys(sgr),
                                    BND_STE_PAR_POS)


# setters
def set_atom_implicit_hydrogen_valences(xgr, atm_imp_hyd_vlc_dct):
    """ set atom implicit hydrogen valences
    """
    atm_dct = mdict.set_by_key_by_position(atoms(xgr), atm_imp_hyd_vlc_dct,
                                           ATM_IMP_HYD_VLC_POS)
    bnd_dct = bonds(xgr)
    return _create.from_atoms_and_bonds(atm_dct, bnd_dct)


def set_atom_stereo_parities(sgr, atm_par_dct):
    """ set atom parities
    """
    atm_dct = mdict.set_by_key_by_position(atoms(sgr), atm_par_dct,
                                           ATM_STE_PAR_POS)
    return _create.from_atoms_and_bonds(atm_dct, bonds(sgr))


def set_bond_orders(rgr, bnd_ord_dct):
    """ set bond orders
    """
    bnd_dct = mdict.set_by_key_by_position(bonds(rgr), bnd_ord_dct,
                                           BND_ORD_POS)
    return _create.from_atoms_and_bonds(atoms(rgr), bnd_dct)


def set_bond_stereo_parities(sgr, bnd_par_dct):
    """ set bond parities
    """
    bnd_dct = mdict.set_by_key_by_position(bonds(sgr), bnd_par_dct,
                                           BND_STE_PAR_POS)
    return _create.from_atoms_and_bonds(atoms(sgr), bnd_dct)


def relabel(xgr, atm_key_dct):
    """ relabel the graph with new atom keys
    """
    orig_atm_keys = atom_keys(xgr)
    assert set(atm_key_dct.keys()) <= orig_atm_keys

    new_atm_key_dct = dict(zip(orig_atm_keys, orig_atm_keys))
    new_atm_key_dct.update(atm_key_dct)

    _relabel_atom_key = new_atm_key_dct.__getitem__

    def _relabel_bond_key(bnd_key):
        return frozenset(map(_relabel_atom_key, bnd_key))

    atm_dct = dict_.transform_keys(atoms(xgr), _relabel_atom_key)
    bnd_dct = dict_.transform_keys(bonds(xgr), _relabel_bond_key)
    return _create.from_atoms_and_bonds(atm_dct, bnd_dct)


# I/O
def string(gra):
    """ write the graph to a string
    """
    # shift to one-indexing when we print
    atm_key_dct = {atm_key: atm_key+1 for atm_key in atom_keys(gra)}
    gra = relabel(gra, atm_key_dct)

    yaml_atm_dct = atoms(gra)
    yaml_bnd_dct = bonds(gra)

    # prepare the atom dictionary
    yaml_atm_dct = dict(sorted(yaml_atm_dct.items()))
    yaml_atm_dct = dict_.transform_values(
        yaml_atm_dct, lambda x: dict(zip(ATM_PROP_NAMES, x)))

    # perpare the bond dictionary
    yaml_bnd_dct = dict_.transform_keys(
        yaml_bnd_dct, lambda x: tuple(sorted(x)))
    yaml_bnd_dct = dict(sorted(yaml_bnd_dct.items()))
    yaml_bnd_dct = dict_.transform_keys(
        yaml_bnd_dct, lambda x: '-'.join(map(str, x)))
    yaml_bnd_dct = dict_.transform_values(
        yaml_bnd_dct, lambda x: dict(zip(BND_PROP_NAMES, x)))

    yaml_gra_dct = {'atoms': yaml_atm_dct, 'bonds': yaml_bnd_dct}

    gra_str = yaml.dump(yaml_gra_dct, default_flow_style=None, sort_keys=False)
    return gra_str


def from_string(gra_str):
    """ read the graph from a string
    """
    yaml_gra_dct = yaml.load(gra_str, Loader=yaml.FullLoader)

    atm_dct = yaml_gra_dct['atoms']
    bnd_dct = yaml_gra_dct['bonds']

    atm_dct = dict_.transform_values(
        atm_dct, lambda x: tuple(map(x.__getitem__, ATM_PROP_NAMES)))

    bnd_dct = dict_.transform_keys(
        bnd_dct, lambda x: frozenset(map(int, x.split('-'))))

    bnd_dct = dict_.transform_values(
        bnd_dct, lambda x: tuple(map(x.__getitem__, BND_PROP_NAMES)))

    gra = _create.from_atoms_and_bonds(atm_dct, bnd_dct)

    # shift back to zero-indexing when we read it in
    atm_key_dct = {atm_key: atm_key-1 for atm_key in atom_keys(gra)}
    gra = relabel(gra, atm_key_dct)

    return gra


if __name__ == '__main__':
    GRA = (
        {0: ('C', 3, None), 1: ('C', 2, None), 2: ('C', 3, None),
         3: ('C', 1, None), 4: ('C', 1, None), 5: ('C', 1, None),
         6: ('C', 1, False), 7: ('C', 1, False), 8: ('O', 0, None)},
        {frozenset({1, 4}): (1, None), frozenset({4, 6}): (1, None),
         frozenset({0, 3}): (1, None), frozenset({2, 6}): (1, None),
         frozenset({6, 7}): (1, None), frozenset({8, 7}): (1, None),
         frozenset({3, 5}): (1, False), frozenset({5, 7}): (1, None)})

    GRA_STR = string(GRA)
    print(GRA_STR)
    # _GRA = from_string(GRA_STR)

    # print(GRA == _GRA)
