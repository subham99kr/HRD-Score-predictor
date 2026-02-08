import numpy as np
from skimage.measure import regionprops
from skimage.feature import graycomatrix, graycoprops


def glcm_features(pixels, levels=16):
    """
    pixels: 1D array of intensities belonging to one cell
    """

    # reshape to square-ish for GLCM
    size = int(np.sqrt(len(pixels)))
    if size < 4:
        return [0, 0, 0, 0]   # too small → neutral texture
    
    img = pixels[:size*size].reshape(size, size)

    # normalize + quantize
    img = img.astype(np.float32)
    img = (img - img.min()) / (img.max() - img.min() + 1e-6)
    img = (img * (levels - 1)).astype(np.uint8)

    glcm = graycomatrix(
        img,
        distances=[1],
        angles=[0],
        levels=levels,
        symmetric=True,
        normed=True
    )

    contrast = graycoprops(glcm, 'contrast')[0, 0]
    homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
    energy = graycoprops(glcm, 'energy')[0, 0]
    correlation = graycoprops(glcm, 'correlation')[0, 0]

    return [contrast, homogeneity, energy, correlation]

def extract_features_single(img, mask):
    
    props_list = regionprops(mask, intensity_image=img)
    
    for props in props_list:
        # ---------- GEOMETRY ----------
        area = props.area
        perimeter = props.perimeter
        circularity = (4 * np.pi * area) / (perimeter**2 + 1e-6)
        
        minr, minc, maxr, maxc = props.bbox
        width = maxc - minc
        height = maxr - minr
        aspect_ratio = height / (width + 1e-6)
        extent = area / (width * height + 1e-6)
        
        solidity = props.solidity
        eccentricity = props.eccentricity

        # equiv_diameter = props.equivalent_diameter
        # pixels = props.intensity_image[props.image]
        equiv_diameter = props.equivalent_diameter_area
        pixels = props.image_intensity[props.image]
        
        mean_intensity = pixels.mean()
        std_intensity = pixels.std()
        min_intensity = pixels.min()
        max_intensity = pixels.max()
        contrast = max_intensity - min_intensity
        
        # ---------- RADIAL INTENSITY (NEW) ----------
        cy, cx = props.centroid
        
        coords = np.column_stack(np.nonzero(props.image))
        coords[:, 0] += minr
        coords[:, 1] += minc
        
        dists = np.sqrt((coords[:, 0] - cy)**2 + (coords[:, 1] - cx)**2)
        max_dist = dists.max() + 1e-6
        
        inner_mask = dists < 0.3 * max_dist      # center region
        outer_mask = dists > 0.7 * max_dist      # perimeter region
        
        if inner_mask.sum() > 0:
            center_mean_intensity = pixels[inner_mask].mean()
        else:
            center_mean_intensity = mean_intensity
        
        if outer_mask.sum() > 0:
            perimeter_mean_intensity = pixels[outer_mask].mean()
        else:
            perimeter_mean_intensity = mean_intensity
        
        center_perimeter_ratio = center_mean_intensity / (perimeter_mean_intensity + 1e-6)
        radial_intensity_drop = center_mean_intensity - perimeter_mean_intensity

        glcm_contrast, glcm_homogeneity, glcm_energy, glcm_corr = glcm_features(pixels)

    return np.array([
        area, perimeter, circularity,
        width, height, aspect_ratio, extent,
        solidity, eccentricity, equiv_diameter,
        mean_intensity, std_intensity, min_intensity, max_intensity, contrast,
        center_mean_intensity,
        perimeter_mean_intensity,
        center_perimeter_ratio,
        radial_intensity_drop,
        glcm_contrast, glcm_homogeneity, glcm_energy, glcm_corr
    ])
