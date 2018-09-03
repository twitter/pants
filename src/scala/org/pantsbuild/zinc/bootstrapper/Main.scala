/**
 * Copyright (C) 2017 Pants project contributors (see CONTRIBUTORS.md).
 * Licensed under the Apache License, Version 2.0 (see LICENSE).
 */

package org.pantsbuild.zinc.bootstrapper

//import java.io.File
//import scala.compat.java8.OptionConverters._
//import com.fasterxml.jackson.databind.ObjectMapper
//import com.fasterxml.jackson.module.scala.DefaultScalaModule
//import com.fasterxml.jackson.module.scala.experimental.ScalaObjectMapper
//import org.pantsbuild.zinc.options.Parsed


object Main {
  val Command = "zinc-bootstrapper"

  def main(args: Array[String]): Unit = {
    val outputPath = "/tmp/practice.jar"
    val settings = Settigns(outputPath, )

    //output: File, compilerBridgeSrc: File, compilerInterface: File, scalaInstance: XScalaInstance,
    BootstrapperUtils.compilerInterface(outputPath)
  }
}

case class Settings(
  output: File,
  compilerBridgeSrc: File,
  compilerInterface: File
)
