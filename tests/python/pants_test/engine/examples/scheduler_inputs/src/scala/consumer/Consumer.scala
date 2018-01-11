package consumer

import producer.Producer

object Consumer {
  def consume(): String = {
    "Consumed " + Producer.produce() + "!"
  }
}

