import chainer
import chainer.functions as F
import matplotlib.pyplot as plt
import numpy as np

from brancher.distributions import NormalDistribution, LogNormalDistribution
from brancher.variables import DeterministicVariable, RandomVariable, ProbabilisticModel
from brancher.standard_variables import NormalVariable, LogNormalVariable
from brancher import inference
import brancher.functions as BF

# Real model
nu_real = 1.
mu_real = -2.
x_real = NormalVariable(mu_real, nu_real, "x_real")

# Normal model
nu = LogNormalVariable(0., 1., "nu")
mu = NormalVariable(0., 10., "mu")
x = NormalVariable(mu, nu, "x")
model = ProbabilisticModel([x])

# # Generate data
data = x_real._get_sample(number_samples=50)

# Observe data
x.observe(data[x_real][:, 0, :])

# Variational model
Qnu = LogNormalVariable(0., 1., "nu", learnable=True)
Qmu = NormalVariable(0., 1., "mu", learnable=True)
model.set_posterior_model(ProbabilisticModel([Qmu, Qnu]))

# Inference
inference.stochastic_variational_inference(model,
                                            number_iterations=100,
                                            number_samples=50,
                                            optimizer=chainer.optimizers.Adam(0.1))
loss_list = model.diagnostics["loss curve"]

# Statistics
posterior_samples = model._get_posterior_sample(5000)
nu_posterior_samples = posterior_samples[nu].data._flatten()
mu_posterior_samples = posterior_samples[mu].data._flatten()

# Two subplots, unpack the axes array immediately
f, (ax1, ax2, ax3, ax4) = plt.subplots(1, 4)
ax1.plot(np.array(loss_list))
ax1.set_title("Convergence")
ax1.set_xlabel("Iteration")
ax2.scatter(mu_posterior_samples, nu_posterior_samples, alpha=0.01)
ax2.scatter(mu_real, nu_real, c="r")
ax2.set_title("Posterior samples (b)")
ax3.hist(mu_posterior_samples, 25)
ax3.axvline(x=mu_real, lw=2, c="r")
ax4.hist(nu_posterior_samples, 25)
ax4.axvline(x=nu_real, lw=2, c="r")
plt.show()