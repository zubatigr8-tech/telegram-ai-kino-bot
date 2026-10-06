class_name PlayerController
extends Node
## O'yinchini klaviatura va ekrandagi tugmalar/joystik orqali boshqaradi.

const ATTACK_ACTIONS := ["jab", "cross", "hook", "uppercut", "low_kick", "high_kick"]

var fighter: Fighter
var joystick: VirtualJoystick


func _physics_process(_delta: float) -> void:
	if fighter == null:
		return
	var mv := Vector2(
		Input.get_axis("move_left", "move_right"),
		Input.get_axis("move_down", "move_up"))
	if joystick and joystick.output.length() > 0.1:
		# Joystikda yuqori = ekran ichiga (y manfiy).
		mv = Vector2(joystick.output.x, -joystick.output.y)
	fighter.move_input = mv
	fighter.set_block(Input.is_action_pressed("block"))

	for a in ATTACK_ACTIONS:
		if Input.is_action_just_pressed(a):
			fighter.request_attack(a)
	if Input.is_action_just_pressed("dodge"):
		fighter.request_dodge()
