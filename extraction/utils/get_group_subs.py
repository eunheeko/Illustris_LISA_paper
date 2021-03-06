"""
MAIN PURPOSE: gather subhalos with black holes and create ``subs_with_bhs.hdf5`` file.
"""
import h5py
import os
import numpy as np
import tqdm

from utils.generalfuncs import get
from utils import SubProcess

try:
    import illpy
    import illpy.groupcat
except ImportError:
    illpy = None


class Get_Group_Subs(SubProcess):
    """
    Get_Group_Subs downloads the necessary group catalog files from the Illustris server. It gathers the information we are interested in and outputs to a file. It then deletes that snapshots group catalog file. This code is designed to pick up where it left off if the downloads time out.

        attributes:
            :param  first_snap_with_bhs - (int) - the first snapshot where black holes appear in the simulation
            :param  additional_keys - list of (str) - keys of interest, not including Snapshot, SubhaloID, or SubhaloLenType
            :param  dir_output - (str) - dir_output to store final files in
            :param  ill_run - (int) - integer representing illustris run
            :param  snaps_to_skip - list of (int) - snapshots that are missing (53, 55 in Illustris-1)

            needed - (bool) - does this code needed to run


        methods:
            download_and_add_file_info
    """

    def __init__(self, core, additional_keys=['SubhaloCM', 'SubhaloMassType', 'SubhaloPos',
                                              'SubhaloSFR', 'SubhaloVelDisp', 'SubhaloWindMass']):
        super().__init__(core)
        # self.dir_output = dir_output
        # self.dir_input = dir_input
        # self.ill_run = 1
        # self.baseurl = 'http://www.illustris-project.org/api/Illustris-1/files/groupcat'

        # Illustris-1 has two missing snapshots (53, 55).
        # self.snaps_to_skip = snaps_to_skip

        # the first three keys need to be Snapshot, SubhaloID, and SubhaloLenType
        self.keys = ['Snapshot', 'SubhaloID', 'SubhaloLenType'] + additional_keys

        # If the download timed out previously, figure out where it left off.
        # If not start with first snapshot.
        fname = self.core.fname_subs_with_bhs()
        if os.path.exists(fname):
            with h5py.File(fname, 'r') as f:
                # max_snap = np.asarray(f['Snapshot'][:]).max()
                have_snaps = np.asarray(f['Snapshot'][:])

            # max_snap = have_snaps.max()
            # min_snap = have_snaps.min()
            # self.start_snap = max_snap + 1
            # self.needed = True

            # if the maximum snap (135) is in there, move on.
            # if max_snap == 135:
            #     print("\tGetGroupSubs file info already complete")
            #     self.needed = False

        else:
            # self.start_snap = self.first_snap_with_bhs
            # self.needed = True
            have_snaps = []

        self.need_snaps = [sn for sn in range(self.core.first_snap_with_bhs, self.max_snap+1)
                           if (sn not in have_snaps) and (sn not in self.core.skip_snaps)]
        num_needed = len(self.need_snaps)
        self.needed = (num_needed > 0)
        print("\tGetGroupSubs needs info from {} files".format(num_needed))
        if self.needed:
            print("\t\t{}...{}".format(self.need_snaps[0], self.need_snaps[-1]))

        return

    def download_and_add_file_info(self):
        """
        Downloads group catalog files for the information desired. It then concatenates all this data into ``subs_with_bhs.hdf5``
        """

        # initialize output dict
        out = {key: [] for key in self.keys}
        fname = self.core.fname_subs_with_bhs()
        fname_old = fname + '.old'

        # for snap in np.arange(self.start_snap, 136):
        # for snap in tqdm.trange(self.start_snap, 136):
        for snap in tqdm.tqdm(self.need_snaps, desc='snapshots'):

            # skip bad snapshots (53, 55 in ill1)
            if snap in self.core.skip_snaps:
                continue

            # if any data has been output to file, gather that data into dict.
            # This method is used in case downloads time out in the middle of the run.
            # if snap > self.start_snap:
            with h5py.File(fname, 'r') as f_out:
                for key in self.keys:
                    out[key] = [f_out[key][:]]

            # Load data for this snapshot and add to dictionary of all snapshots
            try:
                out_snap = self.load_snap_subs_with_bhs(snap, self.keys)
            except OSError as err:
                print("\nERROR: snap {}\n".format(snap))
                print("ERROR: '{}'\n\n".format(err))
                continue

            for key in self.keys:
                out[key].append(out_snap[key])

            # move last dataset and store as backup
            # if snap > self.start_snap:
            os.rename(fname, fname_old)

            # write new file with updated data.
            with h5py.File(fname, 'w') as f:
                for key in self.keys:
                    out[key] = np.concatenate(out[key])
                    f.create_dataset(key, data=out[key], dtype=out[key].dtype.name, chunks=True, compression='gzip', compression_opts=9)

            # print(snap, 'groupcat completed')

        # if all files have been dowloaded, delete backup file
        if snap == 135:
            os.remove(fname_old)

        return

    def load_snap_subs_with_bhs(self, snap, keys):

        # out_snap = {key: [] for key in self.keys}
        out_snap = {}

        base = self.baseurl + '-%i/' % snap
        print('start download of snapshot', snap)
        for key in self.keys:
            # Get these quantities below
            if key == 'SubhaloID' or key == 'Snapshot':
                continue

            # download groupcat in quantity desired
            fp = get(base + '?Subhalo=' + key)

            # gather data from this dataset
            with h5py.File(fp, 'r') as f:
                # Run through SubgaloLenType first.
                # This keeps only subhalos with black holes in them.
                # We add subhalo and snapshot info with this.
                if key == 'SubhaloLenType':
                    trans = f['Subhalo'][key][:]
                    inds_keep = np.where(trans[:, 5] > 0)[0]
                    # out_snap['SubhaloID'].append(inds_keep)
                    # out_snap['Snapshot'].append(np.full((len(inds_keep)), snap))
                    out_snap['SubhaloID'] = inds_keep
                    out_snap['Snapshot'] = np.full((len(inds_keep)), snap)

                # add quantity to output dict
                # out_snap[key].append(f['Subhalo'][key][:][inds_keep])
                out_snap[key] = f['Subhalo'][key][:][inds_keep]

            # remove downloaded file
            os.remove(fp)

        print('end downloads', snap)
        return out_snap


class Get_Group_Subs_Odyssey(Get_Group_Subs):

    def load_snap_subs_with_bhs(self, snap, keys):

        # out_snap = {key: [] for key in self.keys}
        out_snap = {}

        # print("loading subhalos from groupcat for snap {:d}".format(snap))

        # Remove keys not present in raw groupcat (on Odyssey)
        keys = list(keys)
        keys.pop(keys.index('Snapshot'))
        keys.pop(keys.index('SubhaloID'))

        subhalos = illpy.groupcat.loadSubhalos(self.dir_input, snap, fields=keys)
        # print("Loaded groupcat subhalo keys = ", list(subhalos.keys()))

        for key in self.keys:
            # Get these quantities below
            if key == 'SubhaloID' or key == 'Snapshot':
                continue

            # Run through SubgaloLenType first.
            # This keeps only subhalos with black holes in them.
            # We add subhalo and snapshot info with this.
            if key == 'SubhaloLenType':
                # trans = subhalos['Subhalo'][key][:]    # API specific
                trans = subhalos[key][:]
                inds_keep = np.where(trans[:, 5] > 0)[0]
                # out_snap['SubhaloID'].append(inds_keep)    # API specific
                # out_snap['Snapshot'].append(np.full((len(inds_keep)), snap))    # API specific
                out_snap['SubhaloID'] = inds_keep
                out_snap['Snapshot'] = np.full((len(inds_keep)), snap)

            # add quantity to output dict
            # out_snap[key].append(f['Subhalo'][key][:][inds_keep])    # API specific
            out_snap[key] = subhalos[key][:][inds_keep]

        # print("\tsnap {} done".format(snap))
        return out_snap
