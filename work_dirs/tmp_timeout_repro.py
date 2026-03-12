from lesson_feature_extractor.model_features import timeout_rate_from_cases

print('start')
value = timeout_rate_from_cases(0, "def f(x):\n    return x\n", 'f', [[1]], 1.0)
print('value=', value)

