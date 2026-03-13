import time


class PID:
    """位置式PID控制器类"""

    def __init__(self, kp, ki, kd, output_limits=None):
        """
        初始化PID参数
        :param kp: 比例系数
        :param ki: 积分系数
        :param kd: 微分系数
        :param output_limits: 输出限幅，元组 (min, max)
        """
        self.Kp = kp
        self.Ki = ki
        self.Kd = kd
        self.setpoint = 0
        self.actual_value = 0
        self.error = 0
        self.last_error = 0
        self.integral = 0
        self.output = 0
        self.output_limits = output_limits
        self.sample_time = 0
        self.last_time = time.time()

    def compute(self, actual_value):
        """
        计算PID输出
        :param actual_value: 当前过程测量值
        :return: 控制器输出
        """
        current_time = time.time()
        delta_time = current_time - self.last_time
        if delta_time < self.sample_time:
            return self.output
        self.actual_value = actual_value
        self.error = self.setpoint - self.actual_value
        self.integral += self.error * delta_time
        derivative = (self.error - self.last_error) / delta_time if delta_time > 0 else 0
        self.output = self.Kp * self.error + self.Ki * self.integral + self.Kd * derivative
        if self.output_limits is not None:
            min_output, max_output = self.output_limits
            self.output = max(min_output, min(self.output, max_output))
            if self.output == min_output or self.output == max_output:
                self.integral -= self.error * delta_time
        self.last_error = self.error
        self.last_time = current_time
        return self.output

    def set_sample_time(self, sample_time):
        """设置采样时间"""
        self.sample_time = sample_time

    def set_setpoint(self, setpoint):
        """设置目标值"""
        self.setpoint = setpoint

    def reset(self):
        """重置PID控制器状态"""
        self.error = 0
        self.last_error = 0
        self.integral = 0
        self.output = 0
        self.last_time = time.time()


class DualAxisPID:
    """双轴PID控制器类，支持X和Y轴独立控制，包含平滑功能"""

    def __init__(self, kp, ki, kd, windup_guard, smooth_params=None, output_limits_x=None, output_limits_y=None,
                 anti_windup_mode='freeze', backcalc_gain=None):
        """
        初始化双轴PID参数
        :param kp: 比例系数 [kp_x, kp_y]
        :param ki: 积分系数 [ki_x, ki_y]
        :param kd: 微分系数 [kd_x, kd_y]
        :param windup_guard: 积分限幅 [windup_x, windup_y]
        :param smooth_params: 平滑参数 [smooth_x, smooth_y, smooth_deadzone]
        """
        self.kp = {'x': kp[0], 'y': kp[1]}
        self.ki = {'x': ki[0], 'y': ki[1]}
        self.kd = {'x': kd[0], 'y': kd[1]}
        self.windup_guard = {'x': windup_guard[0], 'y': windup_guard[1]}
        self.output_limits = {'x': output_limits_x, 'y': output_limits_y}
        self.anti_windup_mode = anti_windup_mode
        if backcalc_gain is None:
            backcalc_gain = [0.0, 0.0]
        elif not isinstance(backcalc_gain, (list, tuple)):
            backcalc_gain = [backcalc_gain, backcalc_gain]
        self.backcalc_gain = {'x': backcalc_gain[0], 'y': backcalc_gain[1]}
        if smooth_params is None:
            smooth_params = [0.0, 0.0, 0.0, 1.0]
        self.smooth_x = smooth_params[0]
        self.smooth_y = smooth_params[1]
        self.smooth_deadzone = smooth_params[2]
        self.smooth_algorithm = smooth_params[3] if len(smooth_params) > 3 else 1.0
        # ---- 误差滤波 ----
        # 对PID输入误差做EMA平滑，过滤检测框帧间抖动
        self.error_filter_alpha = 0.0    # 0=不滤波(直通), 越大越平滑(0~0.95)
        self._filtered_error = {'x': 0.0, 'y': 0.0}
        self._error_filter_initialized = False
        # ---- 速度滤波 ----
        # 对PID输出做EMA平滑，减少移动抖动
        self.vel_filter_alpha = 0.0      # 0=不滤波(直通), 越大越平滑(0~0.95)
        self._filtered_vel = {'x': 0.0, 'y': 0.0}
        self._vel_filter_initialized = False
        self.reset()

    def reset(self):
        """重置控制器状态"""
        self._last_time = time.time()
        self._last_error = {'x': 0, 'y': 0}
        self._p_term = {'x': 0, 'y': 0}
        self._i_term = {'x': 0, 'y': 0}
        self._d_term = {'x': 0, 'y': 0}
        self._i_max = {'x': self.windup_guard['x'], 'y': self.windup_guard['y']}
        self._i_min = {'x': -self.windup_guard['x'], 'y': -self.windup_guard['y']}
        self._last_integral_increment = {'x': 0, 'y': 0}
        self._last_output = {'x': 0.0, 'y': 0.0}  # Added for smoothing
        self._filtered_error = {'x': 0.0, 'y': 0.0}
        self._error_filter_initialized = False
        self._filtered_vel = {'x': 0.0, 'y': 0.0}
        self._vel_filter_initialized = False

    def _calculate_output(self, axis, error, delta_time):
        """
        计算指定轴的PID输出

        参数:
            axis (str): 轴名称 ('x' 或 'y')
            error (float): 误差值
            delta_time (float): 时间差

        返回:
            float: PID输出值
        """
        self._p_term[axis] = self.kp[axis] * error
        integral_increment = self.ki[axis] * error * delta_time
        self._i_term[axis] += integral_increment
        self._last_integral_increment[axis] = integral_increment
        if self.windup_guard[axis] > 0:
            if self._i_term[axis] > self._i_max[axis]:
                self._i_term[axis] = self._i_max[axis]
            elif self._i_term[axis] < self._i_min[axis]:
                self._i_term[axis] = self._i_min[axis]
        if delta_time > 0:
            self._d_term[axis] = self.kd[axis] * ((error - self._last_error[axis]) / delta_time)
        else:
            self._d_term[axis] = 0
        return self._p_term[axis] + self._i_term[axis] + self._d_term[axis]

    def _apply_smoothing(self, x_output, y_output, error_x, error_y, delta_time):
        """
        应用指数平滑算法
        平滑参数 (smooth_x/y) 被解释为时间常数 (毫秒)
        alpha = dt / (dt + tau)
        """
        error_distance = (error_x ** 2 + error_y ** 2) ** 0.5
        if error_distance <= self.smooth_deadzone:
            self._last_output['x'] = x_output
            self._last_output['y'] = y_output
            return (x_output, y_output)

        try:
            tau_x = float(self.smooth_x) / 1000.0  # ms to seconds
            tau_y = float(self.smooth_y) / 1000.0
        except (ValueError, TypeError):
            tau_x, tau_y = 0.0, 0.0

        if delta_time <= 0.000001:
            alpha_x, alpha_y = 1.0, 1.0
        else:
            alpha_x = delta_time / (delta_time + tau_x) if (delta_time + tau_x) > 0 else 1.0
            alpha_y = delta_time / (delta_time + tau_y) if (delta_time + tau_y) > 0 else 1.0
        
        # Clamp alpha to [0, 1] just in case
        alpha_x = max(0.0, min(1.0, alpha_x))
        alpha_y = max(0.0, min(1.0, alpha_y))

        final_x = alpha_x * x_output + (1.0 - alpha_x) * self._last_output['x']
        final_y = alpha_y * y_output + (1.0 - alpha_y) * self._last_output['y']

        self._last_output['x'] = final_x
        self._last_output['y'] = final_y
        
        return (final_x, final_y)

    def _apply_limits_and_anti_windup(self, axis, unsat_value):
        value = unsat_value
        saturated = False
        limits = self.output_limits.get(axis)
        if limits is not None:
            min_out, max_out = limits
            if value > max_out:
                value = max_out
                saturated = True
            elif value < min_out:
                value = min_out
                saturated = True
        if saturated:
            if self.anti_windup_mode == 'backcalc':
                self._i_term[axis] += self.backcalc_gain[axis] * (value - unsat_value)
            else:
                self._i_term[axis] -= self._last_integral_increment[axis]
            if self.windup_guard[axis] > 0:
                if self._i_term[axis] > self._i_max[axis]:
                    self._i_term[axis] = self._i_max[axis]
                    return value
                if self._i_term[axis] < self._i_min[axis]:
                    self._i_term[axis] = self._i_min[axis]
        return value

    @staticmethod
    def _final_clamp(limits, value):
        if limits is None:
            return value
        min_out, max_out = limits
        if value > max_out:
            return max_out
        if value < min_out:
            return min_out
        return value

    def compute(self, error_x, error_y):
        """
        计算双轴PID输出

        参数:
            error_x (float): X轴误差值
            error_y (float): Y轴误差值

        返回:
            tuple: (x_output, y_output) X轴和Y轴的控制输出
        """
        current_time = time.time()
        delta_time = current_time - self._last_time
        # ---- 误差滤波：EMA平滑输入误差，过滤检测框帧间抖动 ----
        ef_alpha = max(0.0, min(0.95, self.error_filter_alpha))
        if ef_alpha > 0.001:
            if not self._error_filter_initialized:
                self._filtered_error['x'] = error_x
                self._filtered_error['y'] = error_y
                self._error_filter_initialized = True
            else:
                self._filtered_error['x'] = ef_alpha * self._filtered_error['x'] + (1.0 - ef_alpha) * error_x
                self._filtered_error['y'] = ef_alpha * self._filtered_error['y'] + (1.0 - ef_alpha) * error_y
            error_x = self._filtered_error['x']
            error_y = self._filtered_error['y']
        x_output_unsat = self._calculate_output('x', error_x, delta_time)
        y_output_unsat = self._calculate_output('y', error_y, delta_time)

        x_output = self._apply_limits_and_anti_windup('x', x_output_unsat)
        y_output = self._apply_limits_and_anti_windup('y', y_output_unsat)
        x_output, y_output = self._apply_smoothing(x_output, y_output, error_x, error_y, delta_time)
        error_magnitude = (error_x ** 2 + error_y ** 2) ** 0.5
        if error_magnitude < 5.0:
            deadzone_factor = max(0.1, error_magnitude / 5.0)
            x_output *= deadzone_factor
            y_output *= deadzone_factor

        x_output = self._final_clamp(self.output_limits.get('x'), x_output)
        y_output = self._final_clamp(self.output_limits.get('y'), y_output)
        # ---- 速度滤波：EMA平滑输出，减少移动抖动 ----
        vf_alpha = max(0.0, min(0.95, self.vel_filter_alpha))
        if vf_alpha > 0.001:
            if not self._vel_filter_initialized:
                self._filtered_vel['x'] = x_output
                self._filtered_vel['y'] = y_output
                self._vel_filter_initialized = True
            else:
                self._filtered_vel['x'] = vf_alpha * self._filtered_vel['x'] + (1.0 - vf_alpha) * x_output
                self._filtered_vel['y'] = vf_alpha * self._filtered_vel['y'] + (1.0 - vf_alpha) * y_output
            x_output = self._filtered_vel['x']
            y_output = self._filtered_vel['y']
        self._last_error['x'] = error_x
        self._last_error['y'] = error_y
        self._last_time = current_time
        return (x_output, y_output)

    def set_windup_guard(self, windup_guard):
        """
        设置积分限幅值

        参数:
            windup_guard: 积分限幅 [windup_x, windup_y]
        """
        self.windup_guard = {'x': windup_guard[0], 'y': windup_guard[1]}
        self._i_max = {'x': self.windup_guard['x'], 'y': self.windup_guard['y']}
        self._i_min = {'x': -self.windup_guard['x'], 'y': -self.windup_guard['y']}

    def set_pid_params(self, kp=None, ki=None, kd=None):
        """
        动态设置PID参数

        参数:
            kp: 比例系数 [kp_x, kp_y] (可选)
            ki: 积分系数 [ki_x, ki_y] (可选)
            kd: 微分系数 [kd_x, kd_y] (可选)
        """
        if kp is not None:
            self.kp = {'x': kp[0], 'y': kp[1]}
        if ki is not None:
            self.ki = {'x': ki[0], 'y': ki[1]}
        if kd is not None:
            self.kd = {'x': kd[0], 'y': kd[1]}

    def set_output_limits(self, x_limits=None, y_limits=None):
        """设置每轴输出限幅，格式 (min, max) 或 None"""
        if x_limits is not None:
            self.output_limits['x'] = x_limits
        if y_limits is not None:
            self.output_limits['y'] = y_limits

    def set_anti_windup(self, mode='freeze', backcalc_gain=None):
        """设置抗积分饱和策略及反算增益"""
        self.anti_windup_mode = mode
        if backcalc_gain is not None:
            if not isinstance(backcalc_gain, (list, tuple)):
                backcalc_gain = [backcalc_gain, backcalc_gain]
            self.backcalc_gain = {'x': backcalc_gain[0], 'y': backcalc_gain[1]}

    def set_smooth_params(self, smooth_x=None, smooth_y=None, smooth_deadzone=None, smooth_algorithm=None):
        """
        设置平滑参数

        参数:
            smooth_x: X轴平滑值 (可选)
            smooth_y: Y轴平滑值 (可选)
            smooth_deadzone: 平滑禁区半径 (可选)
            smooth_algorithm: 平滑算法强度 (可选)
        """
        if smooth_x is not None:
            self.smooth_x = smooth_x
        if smooth_y is not None:
            self.smooth_y = smooth_y
        if smooth_deadzone is not None:
            self.smooth_deadzone = smooth_deadzone
        if smooth_algorithm is not None:
            self.smooth_algorithm = smooth_algorithm

    def set_error_filter(self, alpha=None):
        """
        设置误差滤波参数

        参数:
            alpha: EMA平滑系数 (0=不滤波, 越大越平滑, 最大0.95)
        """
        if alpha is not None:
            self.error_filter_alpha = max(0.0, min(0.95, float(alpha)))

    def set_vel_filter(self, alpha=None):
        """
        设置速度滤波参数

        参数:
            alpha: EMA平滑系数 (0=不滤波, 越大越平滑, 最大0.95)
        """
        if alpha is not None:
            self.vel_filter_alpha = max(0.0, min(0.95, float(alpha)))

    def get_components(self):
        """
        获取当前PID各项分量

        返回:
            dict: 包含各轴P、I、D分量的字典
        """
        return {'x': {'p': self._p_term['x'], 'i': self._i_term['x'], 'd': self._d_term['x']},
                'y': {'p': self._p_term['y'], 'i': self._i_term['y'], 'd': self._d_term['y']}}


if __name__ == '__main__':
    print('=== 单轴PID控制器示例 ===')
    pid = PID(kp=1.0, ki=0.1, kd=0.05, output_limits=(-100, 100))
    pid.set_setpoint(50)
    actual_value = 0
    for i in range(10):
        output = pid.compute(actual_value)
        actual_value += output * 0.01
        print(f'步骤 {i + 1}: 目标值={pid.setpoint}, 当前值={actual_value:.2f}, 输出={output:.2f}')
    print('\n=== 双轴PID控制器示例 ===')
    dual_pid = DualAxisPID(kp=[0.8, 0.6], ki=[0.01, 0.008], kd=[0.05, 0.06], windup_guard=[50, 50],
                           smooth_params=[0.0, 0.0, 2.0, 1.0])
    target_x, target_y = (100, 80)
    current_x, current_y = (0, 0)
    for i in range(10):
        error_x = target_x - current_x
        error_y = target_y - current_y
        output_x, output_y = dual_pid.compute(error_x, error_y)
        current_x += output_x * 0.01 - current_x * 0.01
        current_y += output_y * 0.01 - current_y * 0.01
        print(
            f'步骤 {i + 1}: X轴({current_x:.2f}/{target_x}), Y轴({current_y:.2f}/{target_y}), 输出X={output_x:.2f}, 输出Y={output_y:.2f}')
    components = dual_pid.get_components()
    print('\n最终PID分量:')
    print(f"X轴 - P:{components['x']['p']:.3f}, I:{components['x']['i']:.3f}, D:{components['x']['d']:.3f}")
    print(f"Y轴 - P:{components['y']['p']:.3f}, I:{components['y']['i']:.3f}, D:{components['y']['d']:.3f}")