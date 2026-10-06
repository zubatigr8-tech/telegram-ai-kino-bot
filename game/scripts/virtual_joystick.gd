class_name VirtualJoystick
extends Node2D
## Ekranning chap qismidagi "suzuvchi" joystik. Multitouch bilan ishlaydi:
## joystikni ushlab turib, o'ng qo'l bilan zarba tugmalarini bosish mumkin.

var rest_position := Vector2(170, 550)
var base_radius := 105.0
var knob_radius := 48.0
## Faqat shu chiziqdan chapda boshlangan teginish joystikka tegishli.
var active_max_x := 560.0

var output := Vector2.ZERO
var _touch_index := -1
var _center := Vector2.ZERO
var _knob := Vector2.ZERO


func _ready() -> void:
	_center = rest_position


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed and _touch_index == -1 and t.position.x < active_max_x and t.position.y > 200.0:
			_touch_index = t.index
			_center = t.position
			_knob = Vector2.ZERO
			output = Vector2.ZERO
			queue_redraw()
		elif not t.pressed and t.index == _touch_index:
			_release()
	elif event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		if d.index == _touch_index:
			_knob = (d.position - _center).limit_length(base_radius)
			output = _knob / base_radius
			queue_redraw()


func _release() -> void:
	_touch_index = -1
	_center = rest_position
	_knob = Vector2.ZERO
	output = Vector2.ZERO
	queue_redraw()


func set_rest_position(p: Vector2) -> void:
	rest_position = p
	if _touch_index == -1:
		_center = p
	queue_redraw()


func _draw() -> void:
	draw_circle(_center, base_radius, Color(1, 1, 1, 0.12))
	draw_arc(_center, base_radius, 0, TAU, 48, Color(1, 1, 1, 0.35), 3.0)
	draw_circle(_center + _knob, knob_radius, Color(1, 1, 1, 0.45))
