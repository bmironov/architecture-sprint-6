## Дополнительная часть задания: динамическая маршрутизация на основании показателей количества запросов в секунду

Для выполнения этого задания использовался [YAML](deployment.yaml) файл.

Скриншоты начальной конфигурации Prometheus:
- [график метрики в интерфейсе Prometheus](sprint6_exercise2extra_prometheus.png);
- [экран метрик](sprint6_exercise2extra_metrics.png).

После настройки новых метрик:
```
$ kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1|jq
{
  "kind": "APIResourceList",
  "apiVersion": "v1",
  "groupVersion": "custom.metrics.k8s.io/v1beta1",
  "resources": [
    {
      "name": "namespaces/http_requests_per_second",
      "singularName": "",
      "namespaced": false,
      "kind": "MetricValueList",
      "verbs": [
        "get"
      ]
    },
    {
      "name": "pods/http_requests_per_second",
      "singularName": "",
      "namespaced": true,
      "kind": "MetricValueList",
      "verbs": [
        "get"
      ]
    }
  ]
}
```

Запуск ```locust``` и постепенное повышение нагрузки:
- [график Locust](sprint6_exercise2extra_locust.png);
- [консоль k8s](sprint6_exercise2extra_k8s.png);
- [вывод клманды ```kubectl describe hpa```](sprint6_exercise2extra_hpa.png).