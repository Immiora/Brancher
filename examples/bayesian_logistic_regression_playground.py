import chainer
import matplotlib.pyplot as plt
import numpy as np

from brancher.variables import DeterministicVariable, ProbabilisticModel
from brancher.standard_variables import NormalVariable, BinomialVariable
from brancher import inference
import brancher.functions as BF

# Data
number_regressors = 2
number_samples = 50
x1_input_variable = np.random.normal(1.5, 1.5, (int(number_samples/2), number_regressors, 1))
x1_labels = 0*np.ones((int(number_samples/2), 1))
x2_input_variable = np.random.normal(-1.5, 1.5, (int(number_samples/2), number_regressors, 1))
x2_labels = 1*np.ones((int(number_samples/2),1))
input_variable = np.concatenate((x1_input_variable, x2_input_variable), axis=0)
labels = np.concatenate((x1_labels, x2_labels), axis=0)

# Probabilistic model
weights = NormalVariable(np.zeros((1, number_regressors)), 0.5*np.ones((1, number_regressors)), "weights")
x = DeterministicVariable(input_variable, "x", is_observed=True)
logit_p = BF.matmul(weights, x)
k = BinomialVariable(1, logit_p=logit_p, name="k")
model = ProbabilisticModel([k])

samples = model.get_sample(300)
model.calculate_log_probability(samples)

# Observations
k.observe(labels)

# Variational Model
Qweights = NormalVariable(np.zeros((1, number_regressors)),
                          np.ones((1, number_regressors)), "weights", learnable=True)
variational_model = ProbabilisticModel([Qweights])

# Inference
loss_list = inference.stochastic_variational_inference(model, variational_model,
                                                       number_iterations=200,
                                                       number_samples=100,
                                                       optimizer=chainer.optimizers.Adam(0.05))

# Statistics
posterior_samples = variational_model.get_sample(100)
weights_posterior_samples = posterior_samples[Qweights].data

# Two subplots, unpack the axes array immediately
f, (ax1, ax2) = plt.subplots(1, 2)
ax1.plot(np.array(loss_list))
ax1.set_title("Convergence")
ax1.set_xlabel("Iteration")
ax2.scatter(input_variable[:,0,0], input_variable[:,1,0], c=labels.flatten())
for w in weights_posterior_samples:
    coeff = -float(w[0,0,0])/float(w[0,0,1])
    x_range = np.linspace(-2,2,200)
    plt.plot(x_range, coeff*x_range, alpha=0.3)
ax2.set_xlim(-2,2)
ax2.set_ylim(-2,2)
plt.show()