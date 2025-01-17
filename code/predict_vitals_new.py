from scipy import signal
import tensorflow as tf
import numpy as np
import scipy.io
import sys
import argparse
sys.path.append('../')
from model import Attention_mask, MTTS_CAN, TS_CAN
import h5py
import matplotlib.pyplot as plt
from scipy.signal import butter
from inference_preprocess import preprocess_raw_video, detrend
from sklearn.preprocessing import MinMaxScaler

import heartpy as hp

def predict_vitals(args):
    mms = MinMaxScaler()
    img_rows = 36
    img_cols = 36
    frame_depth = 10
    #model_checkpoint = './mtts_can.hdf5'
    model_checkpoint = args.trained_model
    batch_size = args.batch_size
    sample_data_path = args.video_path
    print("path:  ",sample_data_path)

    dXsub, fs = preprocess_raw_video(sample_data_path, dim=36)
    print('dXsub shape', dXsub.shape)

    dXsub_len = (dXsub.shape[0] // frame_depth)  * frame_depth
    dXsub = dXsub[:dXsub_len, :, :, :]

    model = TS_CAN(frame_depth, 32, 64, (img_rows, img_cols, 3))
    model.load_weights(model_checkpoint)

    yptest = model.predict((dXsub[:, :, :, :3], dXsub[:, :, :, -3:]), batch_size=batch_size, verbose=1)

    pulse_pred = yptest#[0]
    pulse_pred = detrend(np.cumsum(pulse_pred), 100)
    [b_pulse_pred, a_pulse_pred] = butter(1, [0.75 / fs * 2, 2.5 / fs * 2], btype='bandpass')
    pulse_pred = scipy.signal.filtfilt(b_pulse_pred, a_pulse_pred, np.double(pulse_pred))
    pulse_pred = np.array(mms.fit_transform(pulse_pred.reshape(-1,1))).flatten()
    
    ##### ground truth data resampled  #######
    print("\n", sample_data_path)
    print(str(sample_data_path).find("COHFACE"))
    print(str(sample_data_path).find("UBFC-PHYS"))
    if(str(sample_data_path).find("COHFACE") > 0):
        truth_path = args.video_path.replace(".avi", "_dataFile.hdf5")   # akutell für COHACE...
    elif(str(sample_data_path).find("UBFC-PHYS") > 0):
        print("OK")
        truth_path = args.video_path.replace("vid_", "") + "_dataFile.hdf5"
    else:
        return("Error in finding the ground truth signal...")
    print(truth_path)
    gound_truth_file = h5py.File(truth_path, "r")
    pulse_truth = gound_truth_file["pulse"]   ### range ground truth from 0 to 1
    pulse_truth = detrend(np.cumsum(pulse_truth), 100)
    [b_pulse_tr, a_pulse_tr] = butter(1, [0.75 / fs * 2, 2.5 / fs * 2], btype='bandpass')
    pulse_truth = scipy.signal.filtfilt(b_pulse_tr, a_pulse_tr, np.double(pulse_truth))
    pulse_truth = np.array(mms.fit_transform(pulse_truth.reshape(-1,1))).flatten()
    pulse_truth = pulse_truth[0: dXsub_len]

    ########### Peaks ###########
    working_data_pred, measures_pred = hp.process(pulse_pred, fs, calc_freq=True)
    working_data_truth, measures_truth = hp.process(pulse_truth, fs, calc_freq=True)
    peaks_pred = working_data_pred['peaklist']
    peaks_truth = working_data_truth['peaklist']

    ######## x-axis: time #########
    duration_vid = dXsub_len/fs
    x_axis = np.linspace(0, duration_vid, dXsub_len)

    ########## Plot ##################
    plt.figure() #subplot(211)
    plt.plot(x_axis, pulse_pred, label='Prediction', color ='#E6001A')
    plt.plot(x_axis[peaks_truth], pulse_truth[peaks_truth], "x", color="#721085")
    plt.plot(x_axis[peaks_pred], pulse_pred[peaks_pred], "x", color ='#E6001A')
    plt.title('Pulse Prediction')
    plt.xlabel("time (s)")
    plt.ylabel("normalized Signal [a.u.]")
    plt.plot(x_axis, pulse_truth, label='ground truth', color="#721085")
    plt.legend()

    plt.figure()
    plt.subplot(211)
    plt.plot(x_axis, pulse_truth, label='Ground truth')
    plt.plot(x_axis[peaks_truth], pulse_truth[peaks_truth], "x")
    plt.ylabel("normalized Signal [a.u.]")
    plt.xlabel("time (s)")
    plt.title('Ground truth')
    plt.subplot(212)
    plt.plot(x_axis, pulse_pred, label='Prediction')
    plt.plot(x_axis[peaks_pred], pulse_pred[peaks_pred], "x")
    plt.title("Prediction")
    plt.ylabel("normalized Signal [a.u.]")
    plt.xlabel("time (s)")
    plt.legend()
    plt.show()

    ########### IBI #############
    ibi_truth = working_data_truth['RR_list_cor']
    print(ibi_truth)
    ibi_pred = working_data_pred['RR_list_cor']
    print(ibi_pred)
    ######### HRV featurs ##############
    print("HRV Truth:  ",measures_truth)
    print("HRV Pred:  ", measures_pred)
    ####### Logging #############
    # neuer Ordner für Tests
    file = open(str(sample_data_path).replace(".avi", "_result.txt"),"w")
    file.write("LogFile\n\n")
    file.write("IBI: "), file.write(str(ibi_pred))
    file.write("\nHR and HRVfeatures: "), file.write(str(measures_pred))

    file.write("\n\n\nGround truth infos!")
    file.write("\nHR and HRV features: "), file.write(str(measures_truth))

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--video_path', type=str, help='processed video path')
    parser.add_argument('--batch_size', type=int, default = 100, help='batch size (multiplier of 10)')
    parser.add_argument('--trained_model', type=str, default = './rPPG-checkpoints/testCohFace1/cv_0_epoch24_model.hdf5', help='path to trained model')

    args = parser.parse_args()

    predict_vitals(args)


#python code/predict_vitals_new.py --video_path "D:\Databases\1)Training\COHFACE\1\1\data.avi" --trained_model ./cv_0_epoch24_model.hdf5
#./rPPG-checkpoints/testCohFace1/cv_0_epoch24_model.hdf5
#./rPPG-checkpoints/test1/cv_0_epoch04_model.hdf5'
#python code/predict_vitals_new.py --video_path "D:\Databases\1)Training\UBFC-PHYS\s1\vid_s1_T1.avi" --trained_model ./cv_0_epoch24_model.hdf5