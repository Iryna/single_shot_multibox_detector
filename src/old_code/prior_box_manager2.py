import numpy as np

class PriorBoxManager(object):
    """docstring for PriorBoxManager"""
    def __init__(self, prior_boxes, overlap_threshold=.5, background_id=0,
                 num_classes=21):
        super(PriorBoxManager, self).__init__()
        self.prior_boxes = self._flatten_prior_boxes(prior_boxes)
        self.num_priors = self.prior_boxes.shape[0]
        self.num_classes = num_classes
        self.overlap_threshold = overlap_threshold
        self.background_id = background_id

    def _flatten_prior_boxes(self, prior_boxes):
        prior_boxes = [layer_boxes.reshape(-1, 4)
                       for layer_boxes in prior_boxes]
        prior_boxes = np.concatenate(prior_boxes, axis=0)
        return prior_boxes

    def _calculate_intersection_over_unions(self, ground_truth_data):
        ground_truth_x_min = ground_truth_data[0]
        ground_truth_y_min = ground_truth_data[1]
        ground_truth_x_max = ground_truth_data[2]
        ground_truth_y_max = ground_truth_data[3]
        prior_boxes_x_min = self.prior_boxes[:, 0]
        prior_boxes_y_min = self.prior_boxes[:, 1]
        prior_boxes_x_max = self.prior_boxes[:, 2]
        prior_boxes_y_max = self.prior_boxes[:, 3]
        # calculating the intersection
        intersections_x_min = np.maximum(prior_boxes_x_min, ground_truth_x_min)
        intersections_y_min = np.maximum(prior_boxes_y_min, ground_truth_y_min)
        intersections_x_max = np.minimum(prior_boxes_x_max, ground_truth_x_max)
        intersections_y_max = np.minimum(prior_boxes_y_max, ground_truth_y_max)
        intersected_widths = intersections_x_max - intersections_x_min
        intersected_heights = intersections_y_max - intersections_y_min
        intersected_widths = np.maximum(intersected_widths, 0)
        intersected_heights = np.maximum(intersected_heights, 0)
        intersections = intersected_widths * intersected_heights
        # calculating the union
        prior_box_widths = prior_boxes_x_max - prior_boxes_x_min
        prior_box_heights = prior_boxes_y_max - prior_boxes_y_min
        prior_box_areas = prior_box_widths * prior_box_heights
        ground_truth_width = ground_truth_x_max - ground_truth_x_min
        ground_truth_height = ground_truth_y_max - ground_truth_y_min
        ground_truth_area = ground_truth_width * ground_truth_height
        unions = prior_box_areas + ground_truth_area - intersections
        intersection_over_unions = intersections / unions
        return intersection_over_unions

    def _encode_box(self, assigned_prior_boxes, ground_truth_box):
        d_box_values = assigned_prior_boxes
        d_box_coordinates = d_box_values[:, 0:4]
        d_x_min = d_box_coordinates[:, 0]
        d_y_min = d_box_coordinates[:, 1]
        d_x_max = d_box_coordinates[:, 2]
        d_y_max = d_box_coordinates[:, 3]
        d_center_x = 0.5 * (d_x_min + d_x_max)
        d_center_y = 0.5 * (d_y_min + d_y_max)
        d_width =  d_x_max - d_x_min
        d_height = d_y_max - d_y_min

        g_box_coordinates = ground_truth_box
        g_x_min = g_box_coordinates[0]
        g_y_min = g_box_coordinates[1]
        g_x_max = g_box_coordinates[2]
        g_y_max = g_box_coordinates[3]
        g_width =  g_x_max - g_x_min
        g_height = g_y_max - g_y_min
        g_center_x = 0.5 * (g_x_min + g_x_max)
        g_center_y = 0.5 * (g_y_min + g_y_max)

        g_hat_center_x = (g_center_x - d_center_x) / d_width
        g_hat_center_y = (g_center_y - d_center_y) / d_height
        g_hat_width  = np.log(g_width  / d_width)
        g_hat_height = np.log(g_height / d_height)
        encoded_boxes = np.concatenate([g_hat_center_x.reshape(-1, 1),
                                        g_hat_center_y.reshape(-1, 1),
                                        g_hat_width.reshape(-1, 1),
                                        g_hat_height.reshape(-1, 1)],
                                        axis=1)
        return encoded_boxes

    def assign_boxes2(self, ground_truth_data, encode_box=True):
        """ you need to give a single set of all the prior boxes back,
        you can't give a set of prior boxes for every object in the image.
        """
        num_objects_in_image = ground_truth_data.shape[0]
        assigned_data = np.zeros((self.num_priors, 4 + self.num_classes))
        assigned_data[:, 3 + self.background_id] = 1.0
        # this is incorrect maybe: len(if num_objects_in_image.shape) < 2
        num_objects_in_image = ground_truth_data.shape[0]
        encoded_boxes = np.zeros((num_objects_in_image, self.num_priors, 4 + 1))
        if num_objects_in_image == 0:
            return assigned_data
        for object_arg in range(num_objects_in_image):
            ground_truth_object = ground_truth_data[object_arg]
            ious = self._calculate_intersection_over_unions(ground_truth_object)
            assign_mask = ious > self.overlap_threshold
            if not assign_mask.any():
                assign_mask[ious.argmax()] = True
            encoded_boxes[object_arg, :, -1][assign_mask] = ious[assign_mask]
            #encoded_boxes[:, -1][assign_mask] = ious[assign_mask]
            assigned_priors = self.prior_boxes[assign_mask]
            if encode_box:
                assigned_encoded_priors = self._encode_box(assigned_priors,
                                                        ground_truth_object)
                encoded_boxes[object_arg, assign_mask] = (
                                                    assigned_encoded_priors)
            else:
                encoded_boxes[object_arg, assign_mask] = assigned_priors


        # best_object_iou best_box_for_object
        best_object_iou = np.max(encoded_boxes, axis=0)
        best_object_iou_indices = np.argmax(encoded_boxes, axis=0)
        best_object_iou_mask = best_object_iou > 0
        best_object_iou_indices = best_object_iou_indices[best_object_iou_mask]
        num_assigned_boxes = len(best_object_iou_indices)
        encoded_boxes[:, best_object_iou_mask, :4] = 0

        assigned_data[best_object_iou_mask, :4] = encoded_boxes[
                                                best_object_iou_indices,
                                                np.arange(num_assigned_boxes),
                                                :4]

        assigned_data[best_object_iou_mask, 4] = 0
        assigned_data[best_object_iou_mask, 5:-8] = ground_truth_data[best_object_iou_indices, 4:]
        return assigned_data


    def _assign_boxes_to_object(self, ground_truth_box, return_iou=True):
        ious = self._calculate_intersection_over_unions(ground_truth_box)
        print(np.max(ious))
        encoded_boxes = np.zeros((self.num_priors, 4 + return_iou))
        assign_mask = ious > self.overlap_threshold
        # all the other will contain an iou of zero
        print(np.sum(assign_mask))
        if not assign_mask.any():
            assign_mask[ious.argmax()] = True
        if return_iou:
            encoded_boxes[:, -1][assign_mask] = ious[assign_mask]
        assigned_priors = self.prior_boxes[assign_mask]
        assigned_encoded_priors = self._encode_box(assigned_priors,
                                                   ground_truth_box)
        encoded_boxes[assign_mask, 0:4] = assigned_encoded_priors
        return encoded_boxes.ravel()

    def assign_boxes(self, ground_truth_data):
        assignments = np.zeros((self.num_priors, 4 + self.num_classes + 8))
        assignments[:, 4 + self.background_id] = 1.0
        num_objects_in_image = len(ground_truth_data)
        if num_objects_in_image == 0:
            return assignments
        encoded_boxes = np.apply_along_axis(self._assign_boxes_to_object,
                                            1, ground_truth_data[:, :4])
        # (num_objects_in_image, num_priors, encoded_coordinates + iou)
        encoded_boxes = encoded_boxes.reshape(-1, self.num_priors, 5)
        # we will take the best boxes for every object in the image
        best_iou = encoded_boxes[:, :, -1].max(axis=0)
        best_iou_indices = encoded_boxes[:, :, -1].argmax(axis=0)
        best_iou_mask = best_iou > 0
        best_iou_indices = best_iou_indices[best_iou_mask]
        num_assigned_boxes = len(best_iou_indices)
        encoded_boxes = encoded_boxes[:, best_iou_mask, :]
        #np.arange is needed since you want to do it for every box
        assignments[best_iou_mask, :4] = encoded_boxes[best_iou_indices,
                                                np.arange(num_assigned_boxes),
                                                :4]

        assignments[best_iou_mask, 4] = 0
        assignments[best_iou_mask, 5:-8] = ground_truth_data[best_iou_indices, 4:]
        # background counter
        assignments[:, -8][best_iou_mask] = 1
        return assignments

    def decode_boxes(self, predicted_boxes):
        prior_x_min = self.prior_boxes[:, 0]
        prior_y_min = self.prior_boxes[:, 1]
        prior_x_max = self.prior_boxes[:, 2]
        prior_y_max = self.prior_boxes[:, 3]

        prior_width = prior_x_max - prior_x_min
        prior_height = prior_y_max - prior_y_min
        prior_center_x = 0.5 * (prior_x_max + prior_x_min)
        prior_center_y = 0.5 * (prior_y_max + prior_y_min)

        #rename to g_hat_center_x all the other variables 
        pred_center_x = predicted_boxes[:, 0]
        pred_center_y = predicted_boxes[:, 1]
        pred_width = predicted_boxes[:, 2]
        pred_height = predicted_boxes[:, 3]

        decoded_center_x = pred_center_x * prior_width
        decoded_center_x = decoded_center_x + prior_center_x
        decoded_center_y = pred_center_y * prior_height
        decoded_center_y = decoded_center_y + prior_center_y

        decoded_width = np.exp(pred_width)
        decoded_width = decoded_width * prior_width
        decoded_height = np.exp(pred_height)
        decoded_height = decoded_height * prior_height

        decoded_x_min = decoded_center_x - (0.5 * decoded_width)
        decoded_y_min = decoded_center_y - (0.5 * decoded_height)
        decoded_x_max = decoded_center_x + (0.5 * decoded_width)
        decoded_y_max = decoded_center_y + (0.5 * decoded_height)

        decoded_boxes = np.concatenate((decoded_x_min[:, None],
                                      decoded_y_min[:, None],
                                      decoded_x_max[:, None],
                                      decoded_y_max[:, None]), axis=-1)
        decoded_boxes = np.clip(decoded_boxes, 0.0, 1.0)
        return decoded_boxes
