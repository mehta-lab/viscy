import cv2
import cv2
import numpy as np
from skimage import color
from scipy.fftpack import fft
from skimage.feature import greycomatrix, greycoprops


class FeatureExtractor:

    def __init__(self):
        pass

    def compute_fourier_descriptors(self, image):
        
        # Threshold the image to get binary image
        _, binary = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Check if any contours are found
        if len(contours) == 0:
            return None
        
        # Select the largest contour
        contour = max(contours, key=cv2.contourArea)
        
        # Convert contour to numpy array
        contour = np.squeeze(contour)
        
        # Convert contour to complex numbers
        contour_complex = contour[:, 0] + 1j * contour[:, 1]
        
        # Compute Fourier descriptors
        descriptors = np.fft.fft(contour_complex)
        
        return descriptors

    def analyze_symmetry(self, descriptors):
        # Normalize descriptors
        descriptors = np.abs(descriptors) / np.max(np.abs(descriptors))
        # Check symmetry (for a perfect circle, descriptors should be quite uniform)
        return np.std(descriptors)  # Lower standard deviation indicates higher symmetry

    def otsu_threshold_and_compute_area(image):

        # Apply Otsu's thresholding
        _, thresh_image = cv2.threshold(
            image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Compute the area of the foreground (non-zero pixels)
        foreground_area = np.sum(thresh_image > 0)

        return thresh_image, foreground_area

    def compute_spectral_entropy(image):
        # Convert image to grayscale if it's not already
        if len(image.shape) == 3:
            image = color.rgb2gray(image)

        # Compute the 2D Fourier Transform
        f_transform = fft.fft2(image)

        # Compute the power spectrum
        power_spectrum = np.abs(f_transform) ** 2

        # Compute the probability distribution
        power_spectrum += 1e-10  # Avoid log(0) issues
        prob_distribution = power_spectrum / np.sum(power_spectrum)

        # Compute the spectral entropy
        entropy = -np.sum(prob_distribution * np.log(prob_distribution))

        return entropy

    def compute_glcm_features(image):

        # Compute the GLCM
        distances = [1]  # Distance between pixels
        angles = [0]  # Angle in radians
        glcm = greycomatrix(image, distances, angles, symmetric=True, normed=True)

        # Compute GLCM properties
        contrast = greycoprops(glcm, "contrast")[0, 0]
        dissimilarity = greycoprops(glcm, "dissimilarity")[0, 0]
        homogeneity = greycoprops(glcm, "homogeneity")[0, 0]

        return contrast, dissimilarity, homogeneity

    def detect_edges(image):

        # Apply Canny edge detection
        edges = cv2.Canny(image, 100, 200)

        return edges

    def compute_iqr(image):

        # Compute the interquartile range of pixel intensities
        iqr = np.percentile(image, 75) - np.percentile(image, 25)

        return iqr
    
    def compute_mean_intensity(image):
        
        # Compute the mean pixel intensity
        mean_intensity = np.mean(image)
        
        return mean_intensity
    
    def compute_std_dev(image):
        
        # Compute the standard deviation of pixel intensities
        std_dev = np.std(image)
        
        return std_dev
