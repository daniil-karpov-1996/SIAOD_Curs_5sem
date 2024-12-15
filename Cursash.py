!pip install deap
!pip install xlsxwriter
import pandas as pd
from datetime import datetime, timedelta
import random
from deap import base, creator, tools, algorithms
import xlsxwriter
import matplotlib.pyplot as plt
import time
import copy
import warnings

# Отключение предупреждений DEAP о повторном создании классов
warnings.filterwarnings("ignore", category=RuntimeWarning, message="A class named 'FitnessMin' has already been created and it will be overwritten.")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="A class named 'Individual' has already been created and it will be overwritten.")

# Список реальных остановок Москвы
MOSCOW_STOPS = [
    "Белорусская", "Новокузнецкая", "Киевская", "Павелецкая", "Тверская",
    "Чистые пруды", "Лубянка", "Охотный ряд", "Красные Ворота", "Чёрная речка",
    "Арбатская", "Смоленская", "Таганская", "Курская", "Краснопресненская",
    "Китай-город", "Третьяковская", "Воробьёвы горы", "Баррикадная", "Кропоткинская",
    "Парк культуры", "Нахимовский проспект", "Трубная", "Водный стадион", "ВДНХ",
    "Проспект Вернадского", "Юго-Западная", "Филёвский парк", "Пионерская", "Мякинино",
    "Новослободская"
]

def time_to_minutes(time_str):
    """Конвертирует строку времени 'HH:MM' в количество минут с полуночи."""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m

def minutes_to_time(minutes):
    """Конвертирует количество минут с полуночи в строку времени 'HH:MM'."""
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

class Bus:
    def __init__(self, bus_id, route):
        self.bus_id = bus_id
        self.route = route
        self.schedule = []  # Список поездок: список остановок с временем прибытия [(stop1, time1), (stop2, time2), ...]
        self.assigned_drivers = []  # Список водителей

class Driver:
    class Shift:
        def __init__(self, work, rests):
            self.work = work  # tuple (start_min, end_min)
            self.rest = rests  # list of tuples [(start_min, end_min), ...]

    def __init__(self, driver_id, driver_type):
        self.driver_id = driver_id
        self.driver_type = driver_type  # 1 или 2
        self.shifts = []  # Список смен: list of Shift objects
        self.assigned_buses = []  # Список автобусов

class Route:
    def __init__(self, route_id, stops, average_time_between_stops, peak_duration_variation, offpeak_duration_variation):
        self.route_id = route_id
        self.stops = stops  # Список остановок
        self.average_time_between_stops = average_time_between_stops  # Среднее время между остановками (минуты)
        self.peak_variation = peak_duration_variation  # Вариация времени в пиковое время
        self.offpeak_variation = offpeak_duration_variation  # Вариация времени в непиковое время
        self.schedule = []  # Список расписаний поездок

class Stop:
    def __init__(self, name):
        self.name = name

def generate_random_routes(num_routes=20, stops_pool=MOSCOW_STOPS, min_stops=5, max_stops=15,
                           average_time_between_stops=5):
    routes = []
    for route_id in range(1, num_routes + 1):
        # Выбор случайных остановок для маршрута без повторений
        num_stops = random.randint(min_stops, max_stops)
        stops = random.sample(stops_pool, num_stops)

        # Генерация вариаций времени между остановками
        peak_variation = 2  # ±2 минуты в пиковое время
        offpeak_variation = 5  # ±5 минут в непиковое время

        # Создание объекта Route
        route = Route(
            route_id=route_id,
            stops=[Stop(name=stop) for stop in stops],
            average_time_between_stops=average_time_between_stops,
            peak_duration_variation=peak_variation,
            offpeak_duration_variation=offpeak_variation
        )

        routes.append(route)

    return routes

def generate_route_schedule(route, start_time_min, operation_hours=24, peak_hours=((7, 10), (17, 20))):
    """
    Генерирует расписание для маршрута с учётом загруженности и стартового времени.
    Добавляет как прямые, так и обратные поездки для возвратного маршрута.
    peak_hours: кортеж кортежей, содержащих время начала и окончания пиковых часов.
    start_time_min: количество минут с полуночи, определяющее начальное время первой поездки.
    """
    schedule = []
    current_time_min = start_time_min
    end_time_min = start_time_min + operation_hours * 60

    # Создаём список остановок для прямой и обратной поездки
    forward_stops = route.stops
    backward_stops = list(reversed(route.stops))[1:-1]  # Исключаем первый и последний, чтобы не повторять начальную остановку

    while current_time_min < end_time_min:
        # Прямая поездка
        in_peak = False
        for peak_start, peak_end in peak_hours:
            peak_start_min = peak_start * 60
            peak_end_min = peak_end * 60
            current_time_mod = current_time_min % 1440  # Время в пределах суток
            if peak_start_min <= current_time_mod < peak_end_min:
                in_peak = True
                break

        if in_peak:
            variation = random.randint(-route.peak_variation, route.peak_variation)  # Вариация в пиковое время
        else:
            variation = random.randint(-route.offpeak_variation, route.offpeak_variation)  # Вариация в непиковое время

        # Расчёт общей длительности прямой поездки
        trip_duration = len(forward_stops) * route.average_time_between_stops + variation
        trip_start_min = current_time_min
        trip_end_min = trip_start_min + trip_duration

        # Генерация расписания по остановкам (прямая поездка)
        trip_schedule_forward = []
        trip_time = trip_start_min
        for stop in forward_stops:
            trip_schedule_forward.append((stop.name, minutes_to_time(trip_time)))
            # Прибавляем среднее время между остановками с вариацией
            travel_time_variation = random.randint(-2, 2)
            trip_time += route.average_time_between_stops + travel_time_variation

        schedule.append(trip_schedule_forward)

        # Обратная поездка
        current_time_min = trip_end_min + 10  # Перерыв между маршрутами

        in_peak = False
        for peak_start, peak_end in peak_hours:
            peak_start_min = peak_start * 60
            peak_end_min = peak_end * 60
            current_time_mod = current_time_min % 1440
            if peak_start_min <= current_time_mod < peak_end_min:
                in_peak = True
                break

        if in_peak:
            variation = random.randint(-route.peak_variation, route.peak_variation)
        else:
            variation = random.randint(-route.offpeak_variation, route.offpeak_variation)

        # Расчёт общей длительности обратной поездки
        trip_duration = len(backward_stops) * route.average_time_between_stops + variation
        trip_start_min = current_time_min
        trip_end_min = trip_start_min + trip_duration

        # Генерация расписания по остановкам (обратная поездка)
        trip_schedule_backward = []
        trip_time = trip_start_min
        for stop in backward_stops:
            trip_schedule_backward.append((stop.name, minutes_to_time(trip_time)))
            travel_time_variation = random.randint(-2, 2)
            trip_time += route.average_time_between_stops + travel_time_variation
        # Возвращаемся на начальную остановку
        trip_schedule_backward.append((forward_stops[0].name, minutes_to_time(trip_time)))

        schedule.append(trip_schedule_backward)

        current_time_min = trip_end_min + 10  # Перерыв между маршрутами

    route.schedule = schedule
    return schedule

def manage_buses(routes, min_buses_per_route=10):
    """
    Управляет количеством автобусов, гарантируя минимальное количество автобусов на каждом маршруте.
    Каждому автобусу назначается уникальное стартовое время для равномерного распределения поездок.
    """
    buses = []
    bus_id = 1
    for route in routes:
        # Расчет интервала между стартами автобусов на маршруте
        interval_min = 1440 / min_buses_per_route  # 1440 минут в сутках
        for i in range(min_buses_per_route):
            bus = Bus(bus_id=bus_id, route=route)
            # Расчет стартового времени для автобуса
            start_time_min = 480 + int(i * interval_min)  # Начало в 08:00 (480 минут)
            generate_route_schedule(route, start_time_min)
            # Копируем расписание маршрута для автобуса
            bus.schedule = copy.deepcopy(route.schedule)
            buses.append(bus)
            bus_id += 1
    return buses

def can_assign(driver, bus):
    """
    Проверяет, можно ли назначить автобус водителю без пересечений расписаний и учитывая перерывы.
    """
    # Временные интервалы автобуса
    bus_trips = [(time_to_minutes(trip[0][1]), time_to_minutes(trip[-1][1])) for trip in bus.schedule]

    for trip_bus_start, trip_bus_end in bus_trips:
        can_work = False
        for shift in driver.shifts:
            work_start, work_end = shift.work
            # Проверка, находится ли поездка полностью в рабочем периоде
            if trip_bus_start >= work_start and trip_bus_end <= work_end:
                # Проверка на пересечения с перерывами
                conflict = False
                for rest_start, rest_end in shift.rest:
                    if (trip_bus_start < rest_end and trip_bus_end > rest_start):
                        conflict = True
                        break
                if not conflict:
                    can_work = True
                    break
        if not can_work:
            return False
    return True

def assign_drivers_greedy(buses, initial_driver_count=10):
    """
    Жадный алгоритм для распределения водителей на автобусы.
    Начинает с заданного количества водителей и добавляет новых по мере необходимости.
    Учитывает перерывы водителей в соответствии с их типом.
    """
    drivers = []
    driver_id = 1
    # Инициализация водителей
    for _ in range(initial_driver_count):
        driver_type = random.choice([1, 2])
        driver = Driver(driver_id=driver_id, driver_type=driver_type)
        if driver_type == 1:
            # Тип 1: Рабочий промежуток 08:00-16:00 с обедом 13:00-14:00
            work_start = 480  # 08:00
            work_end = work_start + 480  # 08:00 + 8 часов = 16:00
            driver.shifts.append(Driver.Shift(work=(work_start, work_end), rests=[(780, 840)]))  # Обед 13:00-14:00
        elif driver_type == 2:
            # Тип 2: Рабочий промежуток 08:00-20:00 с перерывами каждые 2 часа
            work_start = 480  # 08:00
            work_end = work_start + 720  # 08:00 + 12 часов = 20:00
            driver.shifts.append(Driver.Shift(work=(work_start, work_end), rests=[(600, 610), (900, 910)]))  # Перерывы 10:00-10:10 и 15:00-15:10
        drivers.append(driver)
        driver_id += 1

    # Сортируем автобусы по времени начала первой поездки для лучшей загрузки
    buses_sorted = sorted(buses, key=lambda bus: time_to_minutes(bus.schedule[0][0][1]))

    for bus in buses_sorted:
        assigned = False
        for driver in drivers:
            if can_assign(driver, bus):
                # Назначение автобуса водителю
                driver.assigned_buses.append(bus)
                bus.assigned_drivers.append(driver.driver_id)
                assigned = True
                break
        if not assigned:
            # Создаем нового водителя
            new_driver_type = random.choice([1, 2])
            new_driver = Driver(driver_id=driver_id, driver_type=new_driver_type)
            if new_driver_type == 1:
                # Тип 1: Рабочий промежуток 08:00-16:00 с обедом 13:00-14:00
                work_start = 480  # 08:00
                work_end = work_start + 480  # 08:00 + 8 часов = 16:00
                new_driver.shifts.append(Driver.Shift(work=(work_start, work_end), rests=[(780, 840)]))  # Обед 13:00-14:00
            elif new_driver_type == 2:
                # Тип 2: Рабочий промежуток 08:00-20:00 с перерывами каждые 2 часа
                work_start = 480  # 08:00
                work_end = work_start + 720  # 08:00 + 12 часов = 20:00
                new_driver.shifts.append(Driver.Shift(work=(work_start, work_end), rests=[(600, 610), (900, 910)]))  # Перерывы 10:00-10:10 и 15:00-15:10
            # Назначение автобуса
            new_driver.assigned_buses.append(bus)
            bus.assigned_drivers.append(new_driver.driver_id)
            drivers.append(new_driver)
            driver_id += 1
    return drivers

def genetic_driver_assignment(buses, population_size=50, generations=100, cxpb=0.7, mutpb=0.2):
    """
    Генетический алгоритм для распределения водителей на автобусы.
    Цель: минимизировать количество водителей при отсутствии пересечений расписаний.
    Учитывает перерывы водителей в соответствии с их типом.
    """
    # Определение максимального количества водителей (каждый автобус имеет уникального водителя)
    max_drivers = len(buses)

    # Проверка, существуют ли уже классы в creator, и удаление их для избежания предупреждений
    if hasattr(creator, "FitnessMin"):
        del creator.FitnessMin
    if hasattr(creator, "Individual"):
        del creator.Individual

    # Создание классов DEAP
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    # Генерация атрибутов: номер водителя для каждого автобуса
    toolbox.register("attr_driver", random.randint, 0, max_drivers-1)
    # Индивидуум: список водителей для каждого автобуса
    toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_driver, n=len(buses))
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    def eval_individual(individual):
        driver_assignments = {}
        penalty = 0
        for bus_idx, driver in enumerate(individual):
            if driver not in driver_assignments:
                driver_assignments[driver] = []
            driver_assignments[driver].append(buses[bus_idx])

        num_drivers = len(driver_assignments)

        # Проверка на пересечения расписаний и перерывы
        for driver, assigned_buses in driver_assignments.items():
            # Определение типа водителя
            driver_type = random.choice([1, 2])  # Предполагаем случайный тип для каждого водителя
            trips = []
            for bus in assigned_buses:
                trips.extend([(time_to_minutes(trip[0][1]), time_to_minutes(trip[-1][1])) for trip in bus.schedule])
            # Сортировка поездок по времени начала
            trips_sorted = sorted(trips, key=lambda x: x[0])
            # Добавление перерывов
            if driver_type == 1:
                # Проверяем наличие обеденного перерыва
                lunch_break = False
                for trip_start, trip_end in trips_sorted:
                    if 780 <= trip_start <= 840 or 780 <= trip_end <= 840:
                        lunch_break = True
                        break
                if not lunch_break:
                    penalty += 1000  # Штраф за отсутствие обеденного перерыва
            elif driver_type == 2:
                # Проверяем наличие 10-минутных перерывов каждые 2-4 часа
                work_time = 0
                last_trip_end = None
                for trip_start, trip_end in trips_sorted:
                    if last_trip_end:
                        gap = trip_start - last_trip_end
                        if gap >= 10:
                            work_time = 0  # Перерыв
                    work_time += trip_end - trip_start
                    if work_time > 240:  # Превышение 4 часов без перерыва
                        penalty += 1000
                        work_time = 0
                    last_trip_end = trip_end

        return (num_drivers + penalty, )

    toolbox.register("evaluate", eval_individual)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=max_drivers-1, indpb=0.05)
    toolbox.register("select", tools.selTournament, tournsize=3)

    population = toolbox.population(n=population_size)
    hof = tools.HallOfFame(1)

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("min", min)
    stats.register("avg", lambda fits: sum(f[0] for f in fits) / len(fits))

    # Запуск эволюции
    algorithms.eaSimple(population, toolbox, cxpb, mutpb, generations, stats=stats, halloffame=hof, verbose=False)

    best_ind = hof[0]

    # Построение распределения водителей
    driver_assignments = {}
    for bus_idx, driver in enumerate(best_ind):
        if driver not in driver_assignments:
            driver_assignments[driver] = []
        driver_assignments[driver].append(buses[bus_idx])

    # Создание объектов Driver
    drivers = []
    driver_id = 1
    for driver_key, assigned_buses in driver_assignments.items():
        driver_type = random.choice([1, 2])  # Предполагаем случайный тип
        driver = Driver(driver_id=driver_id, driver_type=driver_type)
        # Назначение смен и перерывов
        if driver_type == 1:
            # Тип 1: Рабочий промежуток 08:00-16:00 с обедом 13:00-14:00
            work_start = 480  # 08:00
            work_end = work_start + 480  # 08:00 + 8 часов = 16:00
            driver.shifts.append(Driver.Shift(work=(work_start, work_end), rests=[(780, 840)]))  # Обед 13:00-14:00
        elif driver_type == 2:
            # Тип 2: Рабочий промежуток 08:00-20:00 с перерывами каждые 2 часа
            work_start = 480  # 08:00
            work_end = work_start + 720  # 08:00 + 12 часов = 20:00
            driver.shifts.append(Driver.Shift(work=(work_start, work_end), rests=[(600, 610), (900, 910)]))  # Перерывы 10:00-10:10 и 15:00-15:10
        driver.assigned_buses = [bus.bus_id for bus in assigned_buses]
        drivers.append(driver)
        driver_id += 1

    return drivers

def export_to_excel(drivers, routes, buses, filename="schedule.xlsx"):
    workbook = xlsxwriter.Workbook(filename)

    # Лист водителей
    driver_sheet = workbook.add_worksheet("Водители")
    driver_sheet.write(0, 0, "ID водителя")
    driver_sheet.write(0, 1, "Тип водителя")
    driver_sheet.write(0, 2, "Назначенные автобусы")
    driver_sheet.write(0, 3, "График работы")
    driver_sheet.write(0, 4, "График отдыха")

    for i, driver in enumerate(drivers, start=1):
        driver_sheet.write(i, 0, driver.driver_id)
        driver_sheet.write(i, 1, driver.driver_type)
        assigned_bus_ids = [bus for bus in driver.assigned_buses]
        driver_sheet.write(i, 2, ", ".join(map(str, assigned_bus_ids)))

        # Форматирование рабочих периодов
        working_periods = ", ".join([f"{minutes_to_time(shift.work[0])}-{minutes_to_time(shift.work[1])}" for shift in driver.shifts if shift.work[0] != 0 and shift.work[1] != 0])
        driver_sheet.write(i, 3, working_periods)

        # Форматирование перерывов
        resting_periods = ", ".join([f"{minutes_to_time(rest[0])}-{minutes_to_time(rest[1])}" for shift in driver.shifts for rest in shift.rest])
        driver_sheet.write(i, 4, resting_periods)

    # Лист маршрутов
    route_sheet = workbook.add_worksheet("Маршруты")
    route_sheet.write(0, 0, "ID маршрута")
    route_sheet.write(0, 1, "Остановки")
    route_sheet.write(0, 2, "Расписание")
    route_sheet.write(0, 3, "Назначенные автобусы")

    for i, route in enumerate(routes, start=1):
        route_sheet.write(i, 0, route.route_id)
        route_sheet.write(i, 1, ", ".join([stop.name for stop in route.stops]))
        # Форматирование расписания: каждая поездка в новой строке
        formatted_schedule = ""
        for trip in route.schedule:
            trip_str = ", ".join([f"{stop} {time}" for stop, time in trip])
            formatted_schedule += trip_str + "\n"
        route_sheet.write(i, 2, formatted_schedule.strip())
        # Список автобусов на маршруте
        buses_on_route = [bus.bus_id for bus in buses if bus.route.route_id == route.route_id]
        route_sheet.write(i, 3, ", ".join(map(str, buses_on_route)))

    # Лист автобусов
    bus_sheet = workbook.add_worksheet("Автобусы")
    bus_sheet.write(0, 0, "ID автобуса")
    bus_sheet.write(0, 1, "ID маршрута")
    bus_sheet.write(0, 2, "Назначенные водители")
    bus_sheet.write(0, 3, "Расписание")

    for i, bus in enumerate(buses, start=1):
        bus_sheet.write(i, 0, bus.bus_id)
        bus_sheet.write(i, 1, bus.route.route_id)
        assigned_driver_ids = [driver.driver_id for driver in drivers if driver.driver_id in bus.assigned_drivers]
        bus_sheet.write(i, 2, ", ".join(map(str, assigned_driver_ids)))
        # Форматирование расписания: каждая поездка в новой строке
        formatted_bus_schedule = ""
        for trip in bus.schedule:
            trip_str = ", ".join([f"{stop} {time}" for stop, time in trip])
            formatted_bus_schedule += trip_str + "\n"
        bus_sheet.write(i, 3, formatted_bus_schedule.strip())

    # Лист остановок
    stops_sheet = workbook.add_worksheet("Остановки")
    stops_sheet.write(0, 0, "ID маршрута")
    stops_sheet.write(0, 1, "Остановка")
    stops_sheet.write(0, 2, "ID водителя")
    stops_sheet.write(0, 3, "ID автобуса")
    stops_sheet.write(0, 4, "Время прибытия")

    # Инициализируем счетчик строк
    current_row = 1
    for bus in buses:
        for trip in bus.schedule:
            end_flag = 0
            route_id = bus.route.route_id
            driver_ids = []
            drivers_list = []
            for driver in drivers:
                if driver.driver_id in bus.assigned_drivers:
                    driver_ids.append(driver.driver_id)
                    drivers_list.append(driver)
            # Обычно один водитель на автобус, но на всякий случай берем первого
            if driver_ids:
              driver_id = driver_ids[0]
              driver = drivers_list[0]
            else:
              continue
            bus_id = bus.bus_id
            for stop, time in trip:
                for shift in driver.shifts:
                  if shift.work[0] < time_to_minutes(time) < shift.work[1]:
                    stops_sheet.write(current_row, 0, route_id)
                    stops_sheet.write(current_row, 1, stop)
                    stops_sheet.write(current_row, 2, driver_id)
                    stops_sheet.write(current_row, 3, bus_id)
                    stops_sheet.write(current_row, 4, time)
                    current_row += 1
                    end_flag = 1
                    break
            if end_flag == 1:
              break

    # Лист расписания водителей
    driver_schedule_sheet = workbook.add_worksheet("Расписание водителей")
    driver_schedule_sheet.write(0, 0, "ID водителя")
    driver_schedule_sheet.write(0, 1, "Работает/отдыхает")
    driver_schedule_sheet.write(0, 2, "Начало смены")
    driver_schedule_sheet.write(0, 3, "Конец смены")
    driver_schedule_sheet.write(0, 4, "ID автобуса(если работает)")

    current_row = 1
    # Функция для поиска автобуса, которому соответствует рабочий интервал
    def find_bus_for_interval(driver, work_start, work_end):
        # Проверяем все автобусы, назначенные водителю
        for bus_id in driver.assigned_buses:
            for bus in buses:
                if bus.bus_id == bus_id:
                    for trip in bus.schedule:
                        trip_start_min = time_to_minutes(trip[0][1])
                        trip_end_min = time_to_minutes(trip[-1][1])
                        # Проверяем пересечение временного интервала рабочей смены с поездкой
                        # Если поездка пересекается с рабочим интервалом, считаем, что водитель работает на этом автобусе
                        if (trip_start_min <= work_end and trip_end_min >= work_start):
                            return bus.bus_id
        return "отдыхает"

    for driver in drivers:
        for shift in driver.shifts:
            work_start, work_end = shift.work
            # Если рабочий интервал определён
            if work_start != 0 and work_end != 0:
                # Рабочий интервал
                driver_schedule_sheet.write(current_row, 0, driver.driver_id)
                driver_schedule_sheet.write(current_row, 1, "Работает")
                driver_schedule_sheet.write(current_row, 2, minutes_to_time(work_start))
                driver_schedule_sheet.write(current_row, 3, minutes_to_time(work_end))

                # Поиск автобуса для этого интервала
                bus_id = find_bus_for_interval(driver, work_start, work_end)
                driver_schedule_sheet.write(current_row, 4, bus_id)
                current_row += 1

            # Перерывы
            for rest in shift.rest:
                rest_start, rest_end = rest
                driver_schedule_sheet.write(current_row, 0, driver.driver_id)
                driver_schedule_sheet.write(current_row, 1, "Отдыхает")
                driver_schedule_sheet.write(current_row, 2, minutes_to_time(rest_start))
                driver_schedule_sheet.write(current_row, 3, minutes_to_time(rest_end))
                # В этот период водитель не работает, пишем "отдыхает"
                driver_schedule_sheet.write(current_row, 4, "Отдыхает")
                current_row += 1

    workbook.close()

def compare_algorithms(greedy_time, genetic_time):
    """
    Строит график сравнения времени выполнения алгоритмов.
    """
    algorithms = ['Жадный', 'Генетический']
    times = [greedy_time, genetic_time]

    plt.figure(figsize=(8, 6))
    bars = plt.bar(algorithms, times, color=['blue', 'green'])
    plt.xlabel('Алгоритм')
    plt.ylabel('Время выполнения (сек)')
    plt.title('Сравнение времени выполнения алгоритмов распределения водителей')

    # Добавление значений над столбцами
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.4f}', ha='center', va='bottom')

    plt.savefig('algorithm_comparison.png')
    plt.show()

def main():
    # Инициализация данных
    routes = generate_random_routes(num_routes=20)

    # Управление автобусами: минимум 10 автобусов на маршрут
    buses = manage_buses(routes, min_buses_per_route=10)  # 20 маршрутов * 10 автобусов = 200 автобусов

    # Распределение водителей с использованием жадного алгоритма
    start_greedy = time.time()
    drivers_greedy = assign_drivers_greedy(buses, initial_driver_count=10)
    greedy_time = time.time() - start_greedy

    # Копирование автобусов для генетического алгоритма (чтобы водители не назначались одновременно)
    buses_copy = copy.deepcopy(buses)

    # Распределение водителей с использованием генетического алгоритма
    start_genetic = time.time()
    drivers_genetic = genetic_driver_assignment(buses_copy, population_size=100, generations=100, cxpb=0.7, mutpb=0.2)
    genetic_time = time.time() - start_genetic

    # Вывод результатов
    print(f"Жадный алгоритм:")
    print(f"Количество необходимых водителей: {len(drivers_greedy)}")
    print(f"Время выполнения: {greedy_time:.4f} сек\n")

    print(f"Генетический алгоритм:")
    print(f"Количество необходимых водителей: {len(drivers_genetic)}")
    print(f"Время выполнения: {genetic_time:.4f} сек\n")

    # Экспорт результатов в Excel
    export_to_excel(drivers_greedy, routes, buses, filename="schedule_greedy.xlsx")
    export_to_excel(drivers_genetic, routes, buses_copy, filename="schedule_genetic.xlsx")

    # Построение графика сравнения времени выполнения алгоритмов
    compare_algorithms(greedy_time, genetic_time)

if __name__ == "__main__":
    main()