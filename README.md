# architecture-sprint-6

## Задание 1. Проектирование технологической архитектуры

### Вступление

Диаграммы решения представлены в мультистраничном
[draw.io документе](./Exc1/InsureTech_ToBe.drawio), где приведены 3 диаграммы:
- As Is (текущая архитектура);
- To Be high level (целевая многозональная архитектура на высоком уровне);
- To Be zone (более детальная диаграмма компонентов внутри одной зоны).

Главные изменения архитектуры касаются введения:
- многозональности (для обеспечения более высокой отказоустойчивости
инфраструктуры приложения и возможности повышения скорости отклика клиентам
на основе их гео положения);
- физической и логической репликации слоя БД для повышения отказоустойчивости
слоя данных как внутри однй зоны, так между зонами.

На диаграмме показаны только две зоны, но само по себе аппаратное решение
может спокойно выходить как за две зоны внутри одного провайдера, так и за
пределы одного провайдера (например, использовать облака Yandex Cloud, Selectel,
VM Cloud и т.д. одновременно). С добалением каждой новой зоны необходимо будет
настраивать логическую репликацию на уровне БД между этой новой зоной и всеми
существующими.

БД PostgreSQL позволяет одновременно использовать и физическую, и логическую
репликации. Физическая репликация позволяет быстро восстанавливать доступность
слоя БД внутри одной зоны. Это так называемая "Primary-Standby" конфигурация.
Этот же механизм позволяет одновременно внедрить CQRS на уровне HAProxy и
разнести пишущую и читающую нагрузку внутри одной зоны. Таким образом повышая
уровень доступности БД мы можем повысить и быстродействие слоя БД. PostgreSQL
позволяет иметь несколько физических реплик. Это может позволить дальнейшее
повышение пропускной способности БД на выполнение читающей нагрузки приложения,
но с этим и повысить вероятность чтения неактуальных данных из-за задержек в
репликации данных. Управление такой конфигурацией БД можно позволить тому же
Patroni, который можно настроить для автоматического переключения с Primary на
Standby в случае проблем. Это является стандартным "паттерном" в эксплуатации
PostgreSQL в конфигурации физической репликации (primary-standby).

Между зонами на уровне БД предлагается использовать логическую репликацию
PostgreSQL. Это создает конфигурацию Multi-master, где новые данные могут
создаваться в любой зоне с дальнейшим их реплицированием в другие зоны. Тут
надо аккуратно настроить sequences в каждой зоне, чтобы они не пересекались
по диапазонам между зонами, либо использовать UUID в качестве первичного ключа,
тогда такие ID можно генерировать прямо на клиенте и не переживать об их
уникальности между зонами. В итоге такая конфигурация будет поддерживать полную
копию всех данных в каждой зоне. Это будет происходить не моментально, а с
какой-то задержкой на репликацию между зонами. Но все-таки доступность одной
зоны никак не будет влиять на доступность всего бизнеса, а отсутствие данных из
выбывшей зоны будет устранено автоматически при восстановлении сетевой связи с
такой зоной из других зон.

В текущий момент все приложения и сервисы компании работают с одним экземпляром
БД и разделяют свои данные по разным схемам. В случае объема данных в 50 Гб с
точки зрения производительности это ничего страшного не представляет, так как
PostgreSQL полагается на двойное кэширование данных (на уровне ОС и БД). Таким
образом одна виртуальная машина даже с 16 Гб ОЗУ будет работать с большой частью
данных из кэша минуя дисковые операции. Если бюджет компании может позволить
дополнительные расходы на виртуальные машины, то эти схемы данных можно выделить
в отдельные БД, где каждая БД будет существовать в своем кластере PostgreSQL.
Каждая такая БД будет требовать свой набор виртуальных машин для работы реплик
и конфигураций Patroni в каждой зоне. Таким образом расходы на уровень БД
возрастут в 2-3 раза в зависимости от конечного количества независимых
инсталляций PostgreSQL. Возможно с этим общая произволительность сервисов и
вырастет и даже независимость сервисов друг от друга повысится, но будет ли это 
стоить тех затрат на аппаратуру - решать бизнесу. Еще одним фактором для
принятия решения о дроблении БД может стать вполне возможная связь на уровне
данных между схемами. Какие-то таблицы в коде приложения на стороне Java или
бэкенда на PgPLSQL могут спокойно относится к одной схеме, но участвовать в
запросах из других схем. Это обычная практика в устоявшихся монолитах. Таким
образом разделение БД на части может быть не тривиальной задачей на уровне
приложений и потребует дополнительного бюджета на переосмысление общей задачи
и изменение кода.

Применение нескольких зон доступности может позволить достичь практически 100%
доступности приложения для клиентов и при этом иметь возможность обслуживания
всех элементов инфраструктуры, приложений и БД. С помощью GSLB можно выводить
из доступности одну зону, дожидаться прекращения трафика в нее (либо встроить
маршрутизатор в фронтенд / API gateway, которые будут перенаправлять запросы в
одну из доступных зон на момент работ), и проводить необходимые работы в любое
удобное время суток.

Диаграмма "To Be zone" показывает устройство каждой из зон доступности.
Тут мы видим k8s кластер и две виртуальные машины для PostgreSQL. Первая
отвечает за master копию, а вторая - за ее физическую реплику. K8s кластер
состоит из нескольких виртуальных машин. Для простоты показано выполнение по
одному поду каждого из приложений InsureTech на каждой из таких ВМ, где все они
подключаются к БД через HAProxy. Это позволяет решить сразу 2 проблемы:
автоматическое переключение на пишущий сервер БД в случае его переключения и
разделение пишущей и читающей нагрузки на БД. HAProxy может запускаться прямо
на самой ВМ и работать как сервис ОС или запускаться как под k8s. Любой из этих
вариантов позволяет устранить возможность недоступности БД из-за проблем с
HAProxy.

K8s кластер позволяет динамически регулировать доступные ресурсы для приложений.
Если приложение работает как stateless, то тут все будет работать без доработок
кода приложения. В случае если приложение сохраняет статус сессии можно
попробовать добавить stateful маршрутизатор перед приложениями, но скорее всего
это не поможет из-за слишком волатильной натуры кластера k8s. В какой-то мере
эта проблема уже должна быть каким-то образом решена, так как текущая
инфраструктура приложений уже работает на k8s.

Перед входом в каждую из зон трафик проверяется системой борьбы с DDoS и следует
в маршрутизатор, который занимается как регулировкой трафика между подами k8s,
так и лимитированием нагрузки от каждого из клиентов в соответствии с
договорными обязательствами перед ним по предоставляемому объему услуг (например,
количеству API запросов в единицу времени).

### Стратегия масштабирования и отказоустойчивости

Как видно из диаграмм, предлагается горизонтальное масштабирование
инфраструктуры для достижения поставленных целей. Ветрикальное масштабирование
тут никак не поможет, так как все решение завязано на единственную ВМ для
PostgreSQL. В случае проблем с этой ВМ весь бизнес будет остановлен до тех пор
пока этот сервис не будет восстановлен.

Наличие Kubernetes должно позволить наращивать мощность уровня приложений. Там
же рекомендуется настроить и HAProxy.

На превом этапе необходимо настроить физическую реплику БД на отдельной ВМ и
установить Patroni для автоматизации переключения с мастера на реплику. HAProxy
так же будет отслеживать такое переключение автоматически и перенаправлять
приложения на текщий мастер БД. Параллельно с этим можно настроить HAProxy и на
разделение читающей и пишущей нагрузок между копиями БД. Если мощности
физической реплики не хватит (а эта ВМ должна быть такой же как и мастер), то
тут два варианта: увеличить ресурсы на каждой из этих двух ВМ; добавить еще
одну физическую реплику с такими же аппаратными возможностями. Благодаря
относительно небольшому объёму данных (50 Гб) даже при 16 Гб ОЗУ на ВМ за счет
двойного кэширования PostgreSQL скорее всего можно будет держать довольно
большую часть данных и/или индексов в ОЗУ. Это означает, что простым увеличением
ОЗУ на этих ВМ можно попробовать повысить производительность БД без добавления
еще одной реплики и получении более сложной инфраструктуры.

Для увеличения уровня доступности приложения в случае проблем на уровне зоны
предлагается рассмотреть вариант настройки дополнительной одной или более зон
доступности. В этом случае между клиентом и приложением добавляется GSLB, а на
уровне БД добавляется логическая репликация связывающая копии БД во всех зонах.
Это более дорогое решение как с точки зрения расходов на аппаратуру, так и с
точки зрения возможных доработок приложения и структур БД. Не забудем, что
добавление новой зоны может снизить нагрузку на существующие зоны и может
позволить уменьшить ресурсы ВМ в этих зонах.

### Конфигурация развертывания приложений в Kubernetes

Несмотря на то, что Kubernetes поддерживает геораспределенные кластеры, все-таки
идеология "одна зона доступности = один кластер k8s" является более простой в
обслуживании, более быстродействующей (так как поды из одной зоны не ходят в БД
в другой зоне), так и более защищенной. Это так же позволяет использовать и
несколько вендоров облачных ресурсов одновременно. А это может пригодиться для
миграции бизнеса с одного вендора на другого в случае необходимости.

### Балансировка нагрузки

На самом высоком уровне GSLB отвечает за распределение нагрузки между зонами
доступности. Далее идет способность k8s масштабировать количество подов под
приходящую нагрузку. API gateway будет балансировать нагрузку между этими
подами. После этого HAProxy распределяет запросы на чтение на реплику БД, а все
остальные уйдут на мастера.

Каждый из компонентов обязан иметь как мониторинг, так и health check. Проверка
доступности компонента может проверяться разными способами:
- доступность зоны на уровне GSLB;
- liveness, readiness для подов Kubernetes;
- keepalived для HAProxy;
- Patroni для PostgreSQL.

### Стратегия фейловер

На каждом уровне применяется своя фейловер стратегия.

На уровне зоны доступности используется GSLB. На уровне Kubernetes используется
кластер с несколькими хостами. На уровне подов настраивается liveness и
readiness. На уровне подключения к БД используется HAProxy. Для самого HAProxy
используется keepalived. БД контроллирует Patroni и автоматически переключает
на реплику. HAProxy автоматически реагирует на переключение БД с мастера на
реплику.

### Конфигурация БД

На первом этапе (внутри первой зоны доступности) необходимо настроить еще одну
ВМ для работы физической реплики. Это решит 2 проблемы: повысить доступность
уровня БД и возможность использования CQRS. Далее необходимо настроить Patroni
для автоматизации переключения с мастера на реплику. Так же необходимо настроить
HAProxy для автоматического переключения соединения подов приложений с мастера
на реплику.

На втором этапе (вводе дополнительных зон доступности) необходимо настроить
логическую репликацию между БД во всех зонах доступности. Параллельно с этим
необходимо проверить приложение на зависимость от sequence (если есть логическая
зависимости от значение бОльшего sequence как более позднего элемента данных).
В каждой зоне доступности настроить БД на генерацию своего диапазона sequence,
для исключения пересечения значений между зонами.

На третьем этапе (если необходимо разнести приложения из собственных схем в
собственные БД) необходимо настроить новые ВМ для новых БД и их реплик в каждой
из зон доступности. Это заметно поднимет расходы на инфраструктуру. Так же
необходимо проверить приложения на возможные случаи использования данных из
других схем потому что теперь это будет требовать отдельного подключения к
другой БД. И это тоже будут расходы на анализ приложения и внедрение необходимых
изменений как в приложение, так, возможно, и в БД.

Резервное копирование должно осуществляться минимум в два мета: на S3 для
обычных бакапов БД; на S3 как archive WAL логов.

### Шардирование БД

БД достаточно маленькая по своему объему и внедрение в ней шардирование не несет
никаких выгод. Это не позволит резко сократить объем данных с введением новой
зоны доступности. При шардировании невозможно будет иметь возможность отключения
зоны для обслуживания ее компонентов, так как все клиенты, которые завязаны на
данные из этой зоны не смогут использовать сервис InsureTech во время таких
работ. Кроме обычных работ возможны и случаи "обрыва кабеля к ЦОД" или "удар
молнии", когда весь трафик в такой ЦОД либо полностью пропадает, либо вынужден
замедляться из-за перегрузки резервных каналов. Да и вообще, идея привязывания
клиента к конкретной зоне доступности не слишком-то соответствует общему
напрвлению задач развития компании.

Логическая репликация между зонами напротив предоставляет возможность
практически 100% доступности сервиса с возможностью обслуживания инфраструктуры.
Эта конфигурация называется Multi-master и с небольшой задержкой предоставляет
все накопленные данные и изменения всем клиентам.

## Задание 2. Динамическое масштабирование контейнеров

Тест проводился со следующими значениями:
- Number of users (peak concurrency) = 15;
- Ramp up (users started/second) = 5;
- Host = http://localhost:8080;
- Advanced options = 5m.

Запуск теста с предложенным значением ```averageUtilization: 80``` не дал
ожидаемого результата и один под справлился с нагрузкой. Поэтому понизил
значение до ```10```. С этим значением k8s очень быстро стал реагировать на
нагрузку и создавать новые поды.

Результаты выполнения этого задания приведены в следующих файлах:
- [deployment.yaml](./Exc2/deployment.yaml) - файл настроек этого задания для
k8s;
- [hpa.log](./Exc2/hpa.log) - показывает результат ```kubectl get hpa``` во
время теста;
- [Locust_report.html](./Exc2/Locust_report.html) - отчет Locust;
- [replicaset.png](./Exc2/replicaset.png) - копия экрана k8s во время теста.

## Задание 3. Переход на Event-Driven архитектуру

Решение этого задания представлено в следующем [документе](./Exc3/README.md).


