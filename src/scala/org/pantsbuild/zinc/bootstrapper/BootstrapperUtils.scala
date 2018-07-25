/**
 * Copyright (C) 2018 Pants project contributors (see CONTRIBUTORS.md).
 * Licensed under the Apache License, Version 2.0 (see LICENSE).
 */

package org.pantsbuild.zinc.bootstrapper

import java.io.File
import java.net.URLClassLoader

import org.pantsbuild.zinc.util.Util

object BootstrapperUtils {
  val CompilerInterfaceId = "compiler-interface"
  val JavaClassVersion = System.getProperty("java.class.version")

  def scalaInstance(setup: CompilerCacheKey): XScalaInstance = {
    val allJars = scalaLibrary +: scalaCompiler +: scalaExtra
    val allJarsLoader = scalaLoader(allJars)
    val libraryOnlyLoader = scalaLoader(scalaLibrary +: scalaExtra)
    new ScalaInstance(
      scalaVersion(allJarsLoader).getOrElse("unknown"),
      allJarsLoader,
      libraryOnlyLoader,
      scalaLibrary,
      scalaCompiler,
      allJars.toArray,
      None
    )
  }

  def scalaLoader(jars: Seq[File]) =
    new URLClassLoader(
      Path.toURLs(jars),
      sbt.internal.inc.classpath.ClasspathUtilities.rootLoader
    )

  def scalaVersion(scalaLoader: ClassLoader): Option[String] = {
    Util.propertyFromResource("compiler.properties", "version.number", scalaLoader)
  }

  def compilerInterface(
    compilerBridgeSrc: File, compilerInterface: File, scalaInstance: XScalaInstance, log: Logger): File = {
    def compile(targetJar: File): Unit =
      AnalyzingCompiler.compileSources(
        Seq(compilerBridgeSrc),
        targetJar,
        Seq(compilerInterface),
        CompilerInterfaceId,
        new RawCompiler(scalaInstance, ClasspathOptionsUtil.auto, log),
        log
      )
    val dir = setup.cacheDir / interfaceId(scalaInstance.actualVersion)
    val interfaceJar = dir / (CompilerInterfaceId + ".jar")
    if (!interfaceJar.isFile) {
      dir.mkdirs()
      val tempJar = File.createTempFile("interface-", ".jar.tmp", dir)
      try {
        compile(tempJar)
        tempJar.renameTo(interfaceJar)
      } finally {
        tempJar.delete()
      }
    }
    interfaceJar
  }

  def interfaceId(scalaVersion: String) = CompilerInterfaceId + "-" + scalaVersion + "-" + JavaClassVersion
}
