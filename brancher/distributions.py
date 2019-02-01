"""
Distributions
---------
Module description
"""
from abc import ABC, abstractmethod
from collections.abc import Iterable
import copy

import numpy as np
from scipy.special import binom

import torch
from torch import distributions

from brancher.utilities import broadcast_and_squeeze_mixed
from brancher.utilities import broadcast_parent_values
from brancher.utilities import sum_data_dimensions
from brancher.utilities import is_discrete, is_tensor
from brancher.utilities import tensor_range

#TODO: We need asserts checking for the right parameters

class Distribution(ABC):
    """
    Summary
    """
    def __init__(self):
        pass

    def check_parameters(self, **parameters):
        assert all([any([param in parameters for param in parameters_tuple]) if isinstance(parameters_tuple, tuple) else parameters_tuple in parameters
                    for parameters_tuple in self.required_parameters])

    @abstractmethod
    def _calculate_log_probability(self, x, **parameters):
        pass

    @abstractmethod
    def _get_sample(self, **parameters):
        pass

    @abstractmethod
    def _preprocess_parameters_for_log_prob(self, x, **parameters):
        pass

    @abstractmethod
    def _preprocess_parameters_for_sampling(self, **parameters):
        pass

    @abstractmethod
    def _postprocess_sample(self, sample, shape):
        pass

    @abstractmethod
    def _postprocess_log_prob(self, log_prob, number_samples, number_datapoints):
        pass

    def calculate_log_probability(self, x, **parameters): #TODO: Fix shape
        self.check_parameters(**parameters)
        x, parameters, number_samples, number_datapoints = self._preprocess_parameters_for_log_prob(x, **parameters)
        log_prob = self._calculate_log_probability(x, **parameters)
        log_prob = self._postprocess_log_prob(log_prob, number_samples, number_datapoints)
        return sum_data_dimensions(log_prob)

    def get_sample(self, **parameters):
        self.check_parameters(**parameters)
        parameters, shape = self._preprocess_parameters_for_sampling(**parameters)
        pre_sample = self._get_sample(**parameters)
        sample = self._postprocess_sample(pre_sample, shape)
        return sample


class ContinuousDistribution(Distribution):
    pass


class DiscreteDistribution(Distribution):
    pass


class UnivariateDistribution(Distribution):
    """
    Summary
    """

    def _preprocess_parameters_for_sampling(self, **parameters):
        parameters = broadcast_and_squeeze_mixed((), parameters)
        return parameters, None

    def _preprocess_parameters_for_log_prob(self, x, **parameters):
        tuple_x, parameters = broadcast_and_squeeze_mixed(tuple([x]), parameters)
        return tuple_x[0], parameters, None, None #TODO: add proper output here

    def _postprocess_sample(self, sample, shape=None):
        return sample

    def _postprocess_log_prob(self, log_prob, number_samples, number_datapoints):
        return log_prob


class ImplicitDistribution(Distribution):
    """
    Summary
    """

    def _preprocess_parameters_for_sampling(self, **parameters):
        return parameters, None

    def _preprocess_parameters_for_log_prob(self, x, **parameters):
        return x, parameters, None, None #TODO: add proper output here

    def _postprocess_sample(self, sample, shape=None):
        return sample

    def _calculate_log_probability(self, x, **parameters):
        return torch.tensor(np.zeros((1, 1))) #TODO: Implement some checks here

    def _postprocess_log_prob(self, log_pro, number_samples, number_datapoints):
        return log_pro


class VectorDistribution(Distribution):#TODO: Work in progress
    """
    Summary
    """
    # def __init__(self, dimension):
    #     self.dimension = dimension
    #     super().__init__()

    def _preprocess_parameters_for_sampling(self, **parameters): #TODO: the batch dimensions need to be reshaped
        #parameters = broadcast_and_squeeze_mixed((), parameters)
        parameters, number_samples, number_datapoints = broadcast_parent_values(parameters)
        shapes_dict = {par_name: list(par_value.shape)
                       for par_name, par_value in parameters.items()
                       if par_name in self.vector_parameters}
        reshaped_parameters = {par_name: par_value.contiguous().view(size=(shapes_dict[par_name][0], np.prod(shapes_dict[par_name][1:]))) if par_name in self.vector_parameters else par_value
                               for par_name, par_value in parameters.items()}
        shape = tuple([number_samples, number_datapoints] + list(shapes_dict.values())[0][1:])
        return reshaped_parameters, shape

    def _preprocess_parameters_for_log_prob(self, x, **parameters):
        #tuple_x, parameters = broadcast_and_squeeze_mixed(tuple([x]), parameters)
        parameters_and_data = parameters
        parameters_and_data.update({"x_data": x})
        parameters_and_data, number_samples, number_datapoints = broadcast_parent_values(parameters_and_data)
        x = parameters_and_data.pop("x_data")
        return x, parameters_and_data, number_samples, number_datapoints

    def _postprocess_sample(self, sample, shape):
        return sample.contiguous().view(size=shape)

    def _postprocess_log_prob(self, log_pro, number_samples, number_datapoints):
        return log_pro.contiguous().view(size=(number_samples, number_datapoints))


class CategoricalDistribution(VectorDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {("p", "softmax_p")}
        self.optional_parameters = {}
        self.vector_parameters = {"p", "softmax_p"}
        self.matrix_parameters = {}
        self.scalar_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        if "p" in parameters:
            log_prob = distributions.one_hot_categorical.OneHotCategorical(probs=parameters["p"]).log_prob(x)

        elif "softmax_p" in parameters:
            if x.shape == parameters["softmax_p"].shape and tensor_range(x) == {0, 1}:
                log_prob = distributions.one_hot_categorical.OneHotCategorical(logits=parameters["softmax_p"][:, :, 0]).log_prob(x[:, :, 0])
            else:
                log_prob = distributions.categorical.Categorical(logits=parameters["softmax_p"][:, :, 0]).log_prob(x[:, 0, 0])
        else:
            raise ValueError("Either p or " +
                             "softmax_p needs to be provided as input")
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        if "p" in parameters:
            sample = distributions.one_hot_categorical.OneHotCategorical(probs=parameters["p"]).sample()
        elif "softmax_p" in parameters:
            sample = distributions.one_hot_categorical.OneHotCategorical(logits=parameters["softmax_p"]).sample()
        else:
            raise ValueError("Either p or " +
                             "softmax_p needs to be provided as input")
        return sample


class EmpiricalDistribution(ImplicitDistribution): #TODO: It needs to be reworked.
    """
    Summary
    """
    def __init__(self, batch_size, is_observed):
        self.required_parameters = {"dataset"}
        self.optional_parameters = {"indices", "weights"}
        self.batch_size = batch_size
        self.is_observed = is_observed
        super().__init__()

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------
        Returns
        -------
        Without replacement
        """
        dataset = parameters["dataset"]
        if "indices" not in parameters:
            if "weights" in parameters:
                weights = parameters["weights"]
                p = np.array(weights).astype("float64")
                p = p/np.sum(p)
            else:
                p = None
            if is_tensor(dataset):
                if self.is_observed:
                    dataset_size = dataset.shape[1]
                else:
                    dataset_size = dataset.shape[2]
            else:
                dataset_size = len(dataset)
            if dataset_size < self.batch_size:
                raise ValueError("It is impossible to have more samples than the size of the dataset without replacement")
            if is_discrete(dataset): #
                indices = np.random.choice(range(dataset_size), size=self.batch_size, replace=False, p=p)
            else:
                indices = [np.random.choice(range(dataset_size), size=self.batch_size, replace=False, p=p)
                           for _ in range(number_samples)] #TODO IMPORTANT!: This needs to be fixed
        else:
            indices = parameters["indices"]

        if is_tensor(dataset):
            if isinstance(indices, list) and isinstance(indices[0], np.ndarray):
                if self.is_observed:
                    sample = torch.cat([dataset[n, k, :].unsqueeze(dim=0) for n, k in enumerate(indices)], dim=0)
                else:
                    sample = torch.cat([dataset[n, :, k, :].unsqueeze(dim=0) for n, k in enumerate(indices)], dim=0)

            elif isinstance(indices, list) and isinstance(indices[0], (int, np.int32, np.int64)):
                if self.is_observed:
                    sample = dataset[:, indices, :]
                else:
                    sample = dataset[:, :, indices, :]
            else:
                raise IndexError("The indices of an empirical variable should be either a list of integers or a list of arrays")
        else:
            sample = list(np.array(dataset)[indices]) # TODO: This is for allowing discrete data, temporary? For julia
        return sample


class NormalDistribution(ContinuousDistribution, UnivariateDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {"loc", "scale"}
        self.optional_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        log_prob = distributions.normal.Normal(loc=parameters["loc"],
                                               scale=parameters["scale"]).log_prob(x)
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        return distributions.normal.Normal(loc=parameters["loc"],
                                           scale=parameters["scale"]).rsample()


class LogNormalDistribution(ContinuousDistribution, UnivariateDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {"loc", "scale"}
        self.optional_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        log_prob = distributions.log_normal.LogNormal(loc=parameters["loc"],
                                                      scale=parameters["scale"]).log_prob(x)
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        return distributions.log_normal.LogNormal(loc=parameters["loc"],
                                                  scale=parameters["scale"]).rsample()


class CauchyDistribution(ContinuousDistribution, UnivariateDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {"loc", "scale"}
        self.optional_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        log_prob = distributions.cauchy.Cauchy(loc=parameters["loc"],
                                               scale=parameters["scale"]).log_prob(x)
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        return distributions.cauchy.Cauchy(loc=parameters["loc"],
                                           scale=parameters["scale"]).rsample()


class LaplaceDistribution(ContinuousDistribution, UnivariateDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {"loc", "scale"}
        self.optional_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        log_prob = distributions.laplace.Laplace(loc=parameters["loc"],
                                                 scale=parameters["scale"]).log_prob(x)
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        return distributions.laplace.Laplace(loc=parameters["loc"],
                                             scale=parameters["scale"]).rsample()


class BetaDistribution(ContinuousDistribution, UnivariateDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {"alpha", "beta"}
        self.optional_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        log_prob = distributions.beta.Beta(concentration0=parameters["alpha"],
                                           concentration1=parameters["beta"]).log_prob(x)
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        return distributions.beta.Beta(concentration0=parameters["alpha"],
                                       concentration1=parameters["beta"]).rsample()


class BinomialDistribution(UnivariateDistribution, DiscreteDistribution):
    """
    Summary
    """
    def __init__(self):
        self.required_parameters = {"n", ("p", "logit_p")}
        self.optional_parameters = {}
        super().__init__()

    def _calculate_log_probability(self, x, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        if "p" in parameters:
            log_prob = distributions.binomial.Binomial(total_count=parameters["n"],
                                                       probs=parameters["p"]).log_prob(x)

        elif "logit_p" in parameters:
            log_prob = distributions.binomial.Binomial(total_count=parameters["n"],
                                                       logits=parameters["logit_p"]).log_prob(x)
        else:
            raise ValueError("Either p or " +
                             "logit_p needs to be provided as input")
        return log_prob

    def _get_sample(self, **parameters):
        """
        One line description

        Parameters
        ----------

        Returns
        -------
        """
        if "p" in parameters:
            sample = distributions.binomial.Binomial(total_count=parameters["n"],
                                                      probs=parameters["p"]).sample()
        elif "logit_p" in parameters:
            sample = distributions.binomial.Binomial(total_count=parameters["n"],
                                                      logits=parameters["logit_p"]).sample()
        else:
            raise ValueError("Either p or " +
                             "logit_p needs to be provided as input")
        return  sample


# class LogitBinomialDistribution(UnivariateDistribution, DiscreteDistribution):
#     """
#     Summary
#     """
#     def __init__(self):
#         self.required_parameters = {"n", "logit_p"}
#         self.optional_parameters = {}
#         super().__init__()
#
#     def _calculate_log_probability(self, x, **parameters):
#         """
#         One line description
#
#         Parameters
#         ----------
#
#         Returns
#         -------
#         """
#         log_prob = distributions.binomial.Binomial(total_count=parameters["n"],
#                                                    logits=parameters["logit_p"]).log_prob(x)
#         return log_prob
#
#     def _get_sample(self, **parameters):
#         """
#         One line description
#
#         Parameters
#         ----------
#
#         Returns
#         -------
#         """
#         return distributions.binomial.Binomial(total_count=parameters["n"],
#                                                logits=parameters["logit_p"]).sample()
