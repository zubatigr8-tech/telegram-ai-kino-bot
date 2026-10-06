extends SceneTree
## Avtomatik sinov: ikkala jangchini bot boshqaradi, jang oxirigacha o'ynaladi.
## Ishga tushirish:
##   godot --headless --path game --fixed-fps 60 -s res://tests/sim_test.gd

var main: Node
var frames := 0
var hits := {}


func _initialize() -> void:
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)


func _setup() -> void:
	# O'yinchi ham bot bo'ladi
	for c in main.get_children():
		if c is PlayerController:
			c.queue_free()
	var ai := AIController.new()
	ai.fighter = main.player
	ai.difficulty = 0.7
	main.add_child(ai)
	for f in [main.player, main.bot]:
		f.hit_landed.connect(func(_a, _t, _d, kind): hits[kind] = hits.get(kind, 0) + 1)


func _process(_delta: float) -> bool:
	frames += 1
	if frames == 1:
		_setup()
	if main._state == main.MatchState.MATCH_END:
		_report("OK")
		return true
	if frames > 60 * 60 * 6:
		_report("TIMEOUT")
		return true
	return false


func _report(status: String) -> void:
	print("%s after %.1fs game time | round=%d | player hp=%.0f bot hp=%.0f | scores=%s | hits=%s" % [
		status, frames / 60.0, main._round, main.player.health, main.bot.health, main._scores, hits])
