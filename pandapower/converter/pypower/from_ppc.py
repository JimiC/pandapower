# -*- coding: utf-8 -*-

# Copyright (c) 2016 by University of Kassel and Fraunhofer Institute for Wind Energy and Energy
# System Technology (IWES), Kassel. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

from math import pi
from numpy import sign, nan, append, zeros, max, array
from pandas import Series, DataFrame

from pypower import runpf
from pypower import ppoption

import pandapower as pp
try:
    import pplog as logging
except:
    import logging

logger = logging.getLogger(__name__)


def from_ppc(ppc, f_hz=50):
    """
    This function converts pypower case files to pandapower net structure.

    INPUT:

        **ppc** - The pypower case file.

    OPTIONAL:

        **f_hz** - The frequency of the network.

    OUTPUT:

        **net**

    EXAMPLE:

        import pandapower.converter as pc

        from pypower import case4gs

        ppc_net = case4gs.case4gs()

        pp_net = cv.from_ppc(ppc_net, f_hz=60)

    """
    # --- catch common failures
    if Series(ppc['bus'][:, 9] <= 0).any():
        logger.info('There are false baseKV given in the pypower case file.')

    # --- general_parameters
    baseMVA = ppc['baseMVA']  # MVA
    omega = pi * f_hz  # 1/s

    net = pp.create_empty_network(f_hz=f_hz)

    # --- bus data -> create buses, sgen, load, shunt
    for i in range(len(ppc['bus'])):
        # create buses
        pp.create_bus(net, name=int(ppc['bus'][i, 0]), vn_kv=ppc['bus'][i, 9], type="b",
                      zone=ppc['bus'][i, 6], in_service=bool(ppc['bus'][i, 1] != 4),
                      max_vm_pu=ppc['bus'][i, 11], min_vm_pu=ppc['bus'][i, 12])
        # create sgen, load
        if ppc['bus'][i, 2] > 0:
            pp.create_load(net, i, p_kw=ppc['bus'][i, 2]*1e3, q_kvar=ppc['bus'][i, 3]*1e3)
        elif ppc['bus'][i, 2] < 0:
            pp.create_sgen(net, i, p_kw=ppc['bus'][i, 2]*1e3, q_kvar=ppc['bus'][i, 3]*1e3,
                           type="")
        elif ppc['bus'][i, 3] != 0:
            pp.create_load(net, i, p_kw=ppc['bus'][i, 2]*1e3, q_kvar=ppc['bus'][i, 3]*1e3)
        # create shunt
        if ppc['bus'][i, 4] != 0 or ppc['bus'][i, 5] != 0:
            pp.create_shunt(net, i, p_kw=ppc['bus'][i, 4]*1e3,
                            q_kvar=-ppc['bus'][i, 5]*1e3)
    # unused data of ppc: Vm, Va (partwise: in ext_grid), zone

    # --- gen data -> create ext_grid, gen, sgen
    for i in range(len(ppc['gen'])):
        # if in ppc is only one gen -> numpy initially uses one dim array -> change to two dim array
        if len(ppc["gen"].shape) == 1:
            ppc["gen"] = array(ppc["gen"], ndmin=2)
        current_bus_idx = pp.get_element_index(net, 'bus', name=int(ppc['gen'][i, 0]))
        current_bus_type = int(ppc['bus'][current_bus_idx, 1])
        # create ext_grid
        if current_bus_type == 3:
            if len(pp.get_connected_elements(net, 'ext_grid', current_bus_idx)) > 0:
                logger.info('At bus %d an ext_grid already exists. ' % current_bus_idx +
                            'Because of that generator %d ' % i +
                            'is converted not as an ext_grid but as a sgen')
                current_bus_type = 1
            else:
                pp.create_ext_grid(net, bus=current_bus_idx, vm_pu=ppc['gen'][i, 5],
                                   va_degree=ppc['bus'][current_bus_idx, 8],
                                   in_service=bool(ppc['gen'][i, 7] > 0),
                                   max_p_kw=-ppc['gen'][i, 9]*1e3, min_p_kw=-ppc['gen'][i, 8]*1e3,
                                   max_q_kvar=ppc['gen'][i, 3]*1e3,
                                   min_q_kvar=ppc['gen'][i, 4]*1e3)
                if ppc['gen'][i, 4] > ppc['gen'][i, 3]:
                    logger.info('min_q_kvar of gen %d must be less than max_q_kvar but is not.' % i)
                if -ppc['gen'][i, 9] < -ppc['gen'][i, 8]:
                    logger.info('max_p_kw of gen %d must be less than min_p_kw but is not.' % i)
        # create gen
        elif current_bus_type == 2:
            pp.create_gen(net, bus=current_bus_idx, vm_pu=ppc['gen'][i, 5],
                          p_kw=-ppc['gen'][i, 1]*1e3, in_service=bool(ppc['gen'][i, 7] > 0),
                          max_p_kw=-ppc['gen'][i, 9]*1e3, min_p_kw=-ppc['gen'][i, 8]*1e3,
                          max_q_kvar=ppc['gen'][i, 3]*1e3,
                          min_q_kvar=ppc['gen'][i, 4]*1e3, controllable=True)
            if ppc['gen'][i, 4] > ppc['gen'][i, 3]:
                logger.info('min_q_kvar of gen %d must be less than max_q_kvar but is not.' % i)
            if -ppc['gen'][i, 9] < -ppc['gen'][i, 8]:
                logger.info('max_p_kw of gen %d must be less than min_p_kw but is not.' % i)
        # create sgen
        if current_bus_type == 1:
            pp.create_sgen(net, bus=current_bus_idx, p_kw=-ppc['gen'][i, 1]*1e3,
                           q_kvar=-ppc['gen'][i, 2]*1e3, type="",
                           in_service=bool(ppc['gen'][i, 7] > 0),
                           max_p_kw=-ppc['gen'][i, 9]*1e3, min_p_kw=-ppc['gen'][i, 8]*1e3,
                           max_q_kvar=ppc['gen'][i, 3]*1e3,
                           min_q_kvar=ppc['gen'][i, 4]*1e3, controllable=True)
            if ppc['gen'][i, 4] > ppc['gen'][i, 3]:
                logger.info('min_q_kvar of gen %d must be less than max_q_kvar but is not.' % i)
            if -ppc['gen'][i, 9] < -ppc['gen'][i, 8]:
                logger.info('max_p_kw of gen %d must be less than min_p_kw but is not.' % i)
    # unused data of ppc: Vg (partwise: in ext_grid and gen), mBase, Pc1, Pc2, Qc1min, Qc1max,
    # Qc2min, Qc2max, ramp_agc, ramp_10, ramp_30,ramp_q, apf

    # --- branch data -> create line, trafo
    for i in range(len(ppc['branch'])):
        from_bus = pp.get_element_index(net, 'bus', name=int(ppc['branch'][i, 0]))
        to_bus = pp.get_element_index(net, 'bus', name=int(ppc['branch'][i, 1]))

        from_vn_kv = ppc['bus'][from_bus, 9]
        to_vn_kv = ppc['bus'][to_bus, 9]
        if (from_vn_kv == to_vn_kv) & ((ppc['branch'][i, 8] == 0) | (ppc['branch'][i, 8] == 1)):
            Zni = ppc['bus'][to_bus, 9]**2/baseMVA  # ohm

            pp.create_line_from_parameters(
                net, from_bus=from_bus, to_bus=to_bus, length_km=1,
                r_ohm_per_km=ppc['branch'][i, 2]*Zni, x_ohm_per_km=ppc['branch'][i, 3]*Zni,
                c_nf_per_km=ppc['branch'][i, 4]/Zni/omega*1e9/2,
                imax_ka=ppc['branch'][i, 5]/ppc['bus'][to_bus, 9], type='ol',
                in_service=bool(ppc['branch'][i, 10]))

        else:
            if from_vn_kv >= to_vn_kv:
                hv_bus = from_bus
                vn_hv_kv = from_vn_kv
                lv_bus = to_bus
                vn_lv_kv = to_vn_kv
                tp_side = 'hv'
            else:
                hv_bus = to_bus
                vn_hv_kv = to_vn_kv
                lv_bus = from_bus
                vn_lv_kv = from_vn_kv
                tp_side = 'lv'
                if from_vn_kv == to_vn_kv:
                    logger.warn('The pypower branch %d (from_bus, to_bus)=(%d, %d) is considered as'
                                'a transformer because of a ratio != 0 | 1 but it connects the same'
                                ' voltage level', i, ppc['branch'][i, 0], ppc['branch'][i, 1])
            rk = ppc['branch'][i, 2]
            xk = ppc['branch'][i, 3]
            zk = (rk**2+xk**2)**0.5
            sn = ppc['branch'][i, 5]*1e3
            ratio_1 = 0 if ppc['branch'][i, 8] == 0 else (ppc['branch'][i, 8] - 1) * 100
            i0_percent = -ppc['branch'][i, 4]*100*baseMVA*1e3/sn
            if i0_percent < 0:
                logger.info('A transformer always behaves inductive consumpting but the '
                            'susceptance of pypower branch %d (from_bus, to_bus)=(%d, %d) is '
                            'positive.', i, ppc['branch'][i, 0], ppc['branch'][i, 1])

            pp.create_transformer_from_parameters(
                net, hv_bus=hv_bus, lv_bus=lv_bus, sn_kva=sn, vn_hv_kv=vn_hv_kv,
                vn_lv_kv=vn_lv_kv, vsc_percent=zk*sn/1e3, vscr_percent=rk*sn/1e3, pfe_kw=0,
                i0_percent=i0_percent, shift_degree=ppc['branch'][i, 9],
                tp_st_percent=abs(ratio_1) if ratio_1 else nan,
                tp_pos=sign(ratio_1) if ratio_1 else nan,
                tp_side=tp_side if ratio_1 else None, tp_mid=0 if ratio_1 else nan)
    # unused data of ppc: rateB, rateC

    # gencost, areas are currently unconverted

    return net


def validate_from_ppc(ppc_net, pp_net, max_diff_values={
    "vm_pu": 1e-6, "va_degree": 1e-5, "p_branch_kw": 1e-3, "q_branch_kvar": 1e-3, "p_gen_kw": 1e-3,
        "q_gen_kvar": 1e-3}):
    """
    This function validates the pypower case files to pandapower net structure conversion via a \
    comparison of loadflow calculations.

    INPUT:

        **ppc_net** - The pypower case file.

        **pp_net** - The pandapower network.

    OPTIONAL:

        **max_diff_values** - Dict of maximal allowed difference values. The keys must be
            'vm_pu', 'va_degree', 'p_branch_kw', 'q_branch_kvar', 'p_gen_kw' and 'q_gen_kvar' and
            the values floats.

    OUTPUT:

        **conversion_success** - conversion_success is returned as False if pypower or pandapower
            cannot calculate a power flow or if the maximum difference values (max_diff_values )
            cannot be hold.

    EXAMPLE:

        import pandapower.converter as pc

        from pypower import case4gs

        ppc_net = case4gs.case4gs()

        pp_net = cv.from_ppc(ppc_net, f_hz=60)

        cv.validate_from_ppc(ppc_net, pp_net)
    """
    # --- run a pypower power flow
    ppopt = ppoption.ppoption(VERBOSE=0, OUT_ALL=0)
    ppc_res = runpf.runpf(ppc_net, ppopt)[0]

    # --- store pypower power flow results
    ppc_res_branch = ppc_res['branch'][:, 13:17]
    ppc_res_bus = ppc_res['bus'][:, 7:9]
    ppc_res_gen = ppc_res['gen'][:, 1:3]

    # --- try to run a pandapower power flow
    try:
        pp.runpp(pp_net, init="dc", calculate_voltage_angles=True, trafo_model="pi")
    except:
        try:
            pp.runpp(pp_net, calculate_voltage_angles=True, trafo_model="pi")
        except:
            try:
                pp.runpp(pp_net, trafo_model="pi")
            except:
                if (ppc_res['success'] == 1) & (~pp_net.converged):
                    logger.debug('The validation of ppc conversion fails because the pandapower net'
                                 ' power flow do not convert.')
                elif (ppc_res['success'] != 1) & (pp_net.converged):
                    logger.debug('The validation of ppc conversion fails because the power flow of '
                                 'the pypower case do not convert.')
                elif (ppc_res['success'] != 1) & (~pp_net.converged):
                    logger.debug('The power flow of both, the pypower case and the pandapower net, '
                                 'do not convert.')
                return False

    # --- prepare power flow result comparison by reordering pp results as they are in ppc results
    if (ppc_res['success'] == 1) & (pp_net.converged):
        # pandapower bus result table
        pp_res_bus = array(pp_net.res_bus[['vm_pu', 'va_degree']])
        # consideration of parallel generators
        GEN = DataFrame(ppc_res['gen'][:, [0]])
        GEN_uniq = GEN.drop_duplicates(subset=[0])
        # pandapower gen result table
        pp_res_gen = zeros([1, 2])
        change_q_compare = []
        for i in GEN_uniq.index:
            current_bus_idx = pp.get_element_index(pp_net, 'bus', name=int(ppc_res['gen'][i, 0]))
            current_bus_type = int(ppc_res['bus'][current_bus_idx, 1])
            # ext_grid
            if current_bus_type == 3:
                len_start = len(pp_res_gen)
                pp_res_gen = append(pp_res_gen, array(pp_net.res_ext_grid[
                    pp_net.ext_grid.bus == current_bus_idx][['p_kw', 'q_kvar']]), 0)
                pp_res_gen = append(pp_res_gen, array(pp_net.res_sgen[
                    pp_net.sgen.bus == current_bus_idx][['p_kw', 'q_kvar']]), 0)
                len_end = len(pp_res_gen)
                if len_end - len_start > 1:
                    change_q_compare += list(range(len_start-1, len_end-1))
            # gen
            elif current_bus_type == 2:
                len_start = len(pp_res_gen)
                pp_res_gen = append(pp_res_gen, array(pp_net.res_gen[
                    pp_net.gen.bus == current_bus_idx][['p_kw', 'q_kvar']]), 0)
                len_end = len(pp_res_gen)
                if len_end - len_start > 1:
                    change_q_compare += list(range(len_start-1, len_end-1))
            # sgen
            if current_bus_type == 1:
                pp_res_gen = append(pp_res_gen, array(pp_net.res_sgen[
                    pp_net.sgen.bus == current_bus_idx][['p_kw', 'q_kvar']]), 0)
        pp_res_gen = pp_res_gen[1:, :]
        # consideration of parallel branches
        BRANCHES = DataFrame(ppc_res['branch'][:, [0, 1]])
        BRANCHES_uniq = BRANCHES.drop_duplicates()
        # pandapower branch result table
        pp_res_branch = zeros([1, 4])
        for i in BRANCHES_uniq.index:
            from_bus = pp.get_element_index(pp_net, 'bus', name=int(ppc_res['branch'][i, 0]))
            to_bus = pp.get_element_index(pp_net, 'bus', name=int(ppc_res['branch'][i, 1]))
            from_vn_kv = ppc_res['bus'][from_bus, 9]
            to_vn_kv = ppc_res['bus'][to_bus, 9]
            if (from_vn_kv == to_vn_kv) & ((ppc_res['branch'][i, 8] == 0) |
                                           (ppc_res['branch'][i, 8] == 1)):
                pp_res_branch = append(pp_res_branch, array(pp_net.res_line[
                    (pp_net.line.from_bus == from_bus) & (pp_net.line.to_bus == to_bus)]
                        [['p_from_kw', 'q_from_kvar', 'p_to_kw', 'q_to_kvar']]), 0)
            else:
                if from_vn_kv >= to_vn_kv:
                    hv_bus = from_bus
                    lv_bus = to_bus
                    pp_res_branch = append(pp_res_branch, array(pp_net.res_trafo[
                        (pp_net.trafo.hv_bus == hv_bus) & (pp_net.trafo.lv_bus == lv_bus)]
                            [['p_hv_kw', 'q_hv_kvar', 'p_lv_kw', 'q_lv_kvar']]), 0)
                else:
                    hv_bus = to_bus
                    lv_bus = from_bus
                    pp_res_branch = append(pp_res_branch, array(pp_net.res_trafo[
                        (pp_net.trafo.hv_bus == hv_bus) & (pp_net.trafo.lv_bus == lv_bus)]
                            [['p_lv_kw', 'q_lv_kvar', 'p_hv_kw', 'q_hv_kvar']]), 0)
        pp_res_branch = pp_res_branch[1:, :]

        # --- do the power flow result comparison
        diff_res_bus = ppc_res_bus - pp_res_bus
        diff_res_branch = ppc_res_branch - pp_res_branch*1e-3
        diff_res_gen = ppc_res_gen + pp_res_gen*1e-3
        # only compare q of buses with several generation units as sum
        for i in GEN_uniq.index[GEN_uniq.index.isin(change_q_compare)]:
            next_is = GEN_uniq.index[GEN_uniq.index > i]
            if len(next_is) > 0:
                next_i = next_is[0]
            else:
                next_i = GEN.index[-1] + 1
            if (next_i - i) > 1:
                diff_res_gen[i:next_i, 1] = sum(diff_res_gen[i:next_i, 1])
        # logger info
        logger.debug("Maximum voltage magnitude difference between pypower and pandapower: "
                     "%.2e pu" % max(abs(diff_res_bus[:, 0])))
        logger.debug("Maximum voltage angle difference between pypower and pandapower: "
                     "%.2e degree" % max(abs(diff_res_bus[:, 1])))
        logger.debug("Maximum branch flow active power difference between pypower and pandapower: "
                     "%.2e kW" % max(abs(diff_res_branch[:, [0, 2]]*1e3)))
        logger.debug("Maximum branch flow reactive power difference between pypower and "
                     "pandapower: %.2e kVAr" % max(abs(diff_res_branch[:, [1, 3]]*1e3)))
        logger.debug("Maximum active power generation difference between pypower and pandapower: "
                     "%.2e kW" % max(abs(diff_res_gen[:, 0]*1e3)))
        logger.debug("Maximum reactive power generation difference between pypower and pandapower: "
                     "%.2e kVAr" % max(abs(diff_res_gen[:, 1]*1e3)))
        if (max(abs(diff_res_bus[:, 0])) < 1e-3) & (max(abs(diff_res_bus[:, 1])) < 1e-3) & \
           (max(abs(diff_res_branch[:, [0, 2]])) < 1e-3) & \
           (max(abs(diff_res_branch[:, [1, 3]])) < 1e-3) & \
           (max(abs(diff_res_gen)) > 1e-1).any():
                logger.debug("The active/reactive power generation difference possibly results "
                             "because of a pypower fault. If you have an access, please validate "
                             "the results via matpower loadflow.")  # this occurs e.g. at case9

        if type(max_diff_values) == dict:
            if Series(['q_gen_kvar', 'p_branch_kw', 'q_branch_kvar', 'p_gen_kw', 'va_degree',
                       'vm_pu']).isin(Series(list(max_diff_values.keys()))).all():
                if (max(abs(diff_res_bus[:, 0])) < max_diff_values['vm_pu']) & \
                   (max(abs(diff_res_bus[:, 1])) < max_diff_values['va_degree']) & \
                   (max(abs(diff_res_branch[:, [0, 2]])) < max_diff_values['p_branch_kw']/1e3) & \
                   (max(abs(diff_res_branch[:, [1, 3]])) < max_diff_values['q_branch_kvar']/1e3) & \
                   (max(abs(diff_res_gen[:, 0])) < max_diff_values['p_gen_kw']/1e3) & \
                   (max(abs(diff_res_gen[:, 1])) < max_diff_values['q_gen_kvar']/1e3):
                    return True
                else:
                    return False
            else:
                logger.debug('Not all requried dict keys are provided.')
        else:
            logger.debug("'max_diff_values' must be a dict.")

if __name__ == '__main__':
    pass
