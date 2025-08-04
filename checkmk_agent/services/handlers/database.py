"""
Specialized parameter handler for database monitoring services.

Supports major databases (Oracle, MySQL, PostgreSQL, MongoDB, MSSQL) with
database-specific metrics, appropriate default thresholds, and complex
parameter structures.
"""

import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

from .base import BaseParameterHandler, HandlerResult, ValidationSeverity


@dataclass
class DatabaseProfile:
    """Database-specific monitoring profile."""

    db_type: str
    description: str
    common_metrics: List[str]
    default_parameters: Dict[str, Any]
    connection_parameters: List[str]
    performance_parameters: List[str]


class DatabaseParameterHandler(BaseParameterHandler):
    """
    Specialized handler for database monitoring parameters.

    Supports:
    - Major database systems (Oracle, MySQL, PostgreSQL, MongoDB, MSSQL, etc.)
    - Database-specific metrics and thresholds
    - Connection parameter validation
    - Performance monitoring configuration
    - Tablespace, connection, and lock monitoring
    - Database-appropriate default thresholds
    """

    # Database profiles with specific parameters and defaults
    DATABASE_PROFILES = {
        "oracle": DatabaseProfile(
            db_type="oracle",
            description="Oracle Database monitoring",
            common_metrics=[
                "tablespaces",
                "sessions",
                "locks",
                "archive_logs",
                "instance",
                "asm",
            ],
            default_parameters={
                "tablespaces": {
                    "levels": (80.0, 90.0),  # % used
                    "magic_normsize": 100,  # GB
                    "magic": 0.9,
                    "perfdata": True,
                },
                "sessions": {
                    "levels": (80.0, 90.0),  # % of max sessions
                    "absolute_levels": (500, 600),  # Absolute session count
                },
                "locks": {
                    "levels": (80.0, 90.0),  # % of max locks
                    "timeout_levels": (30, 60),  # Lock wait timeout in seconds
                },
                "archive_logs": {
                    "levels": (80.0, 90.0),  # % archive log space used
                    "count_levels": (50, 100),  # Number of archive logs
                },
                "redo_logs": {
                    "switch_rate": (10, 20),  # Log switches per hour
                    "size_levels": (80.0, 90.0),  # % redo log space used
                },
                "sga": {
                    "levels": (80.0, 90.0),  # % SGA memory used
                    "hit_rate": (95.0, 90.0),  # Buffer cache hit rate %
                },
                "pga": {
                    "levels": (80.0, 90.0),  # % PGA memory used
                    "aggregate_target": True,  # Monitor PGA aggregate target
                },
                "instance": {
                    "connection_timeout": 30,
                    "query_timeout": 60,
                    "retry_count": 3,
                },
            },
            connection_parameters=[
                "hostname",
                "port",
                "sid",
                "service_name",
                "username",
                "password",
            ],
            performance_parameters=[
                "sga_target",
                "pga_target",
                "shared_pool_size",
                "buffer_cache_size",
            ],
        ),
        "mysql": DatabaseProfile(
            db_type="mysql",
            description="MySQL/MariaDB monitoring",
            common_metrics=[
                "connections",
                "innodb",
                "replication",
                "slow_queries",
                "table_locks",
            ],
            default_parameters={
                "connections": {
                    "levels": (80.0, 90.0),  # % of max connections
                    "absolute_levels": (150, 200),
                },
                "innodb": {
                    "buffer_pool_hit_rate": (90.0, 95.0),  # Hit rate %
                    "dirty_pages": (80.0, 90.0),  # % dirty pages
                    "lock_waits": (10, 50),  # Lock waits per second
                },
                "replication": {
                    "lag_levels": (60, 300),  # Seconds behind master
                    "io_thread": True,  # Check IO thread status
                    "sql_thread": True,  # Check SQL thread status
                },
                "slow_queries": {
                    "rate_levels": (1.0, 5.0),  # Slow queries per second
                    "percentage_levels": (1.0, 5.0),  # % of total queries
                },
            },
            connection_parameters=[
                "hostname",
                "port",
                "database",
                "username",
                "password",
                "socket",
            ],
            performance_parameters=[
                "innodb_buffer_pool_size",
                "query_cache_size",
                "max_connections",
            ],
        ),
        "postgresql": DatabaseProfile(
            db_type="postgresql",
            description="PostgreSQL monitoring",
            common_metrics=[
                "connections",
                "locks",
                "bgwriter",
                "replication",
                "vacuum",
                "databases",
            ],
            default_parameters={
                "connections": {
                    "levels": (80.0, 90.0),  # % of max connections
                    "absolute_levels": (90, 100),
                },
                "locks": {
                    "levels": (50, 100),  # Number of locks
                    "waiting_levels": (5, 10),  # Waiting locks
                },
                "bgwriter": {
                    "checkpoint_levels": (300, 600),  # Checkpoints per hour
                    "buffer_levels": (80.0, 90.0),  # Buffer hit rate %
                },
                "replication": {
                    "lag_levels": (
                        1024 * 1024,
                        10 * 1024 * 1024,
                    ),  # Bytes behind primary
                    "slot_levels": (80.0, 90.0),  # Replication slot usage %
                },
                "vacuum": {
                    "age_levels": (1000000000, 1500000000),  # Transaction age
                    "analyze_levels": (86400, 172800),  # Seconds since last analyze
                },
            },
            connection_parameters=[
                "hostname",
                "port",
                "database",
                "username",
                "password",
            ],
            performance_parameters=[
                "shared_buffers",
                "work_mem",
                "maintenance_work_mem",
                "max_connections",
            ],
        ),
        "mongodb": DatabaseProfile(
            db_type="mongodb",
            description="MongoDB monitoring",
            common_metrics=[
                "connections",
                "replication",
                "collections",
                "indexes",
                "operations",
            ],
            default_parameters={
                "connections": {
                    "levels": (80.0, 90.0),  # % of max connections
                    "available_levels": (10, 5),  # Available connections
                },
                "replication": {
                    "lag_levels": (10, 30),  # Replication lag in seconds
                    "health_check": True,
                    "priority_levels": (0.5, 0.1),  # Priority thresholds
                },
                "collections": {
                    "size_levels": (80.0, 90.0),  # % of allocated space
                    "index_size_levels": (50.0, 70.0),  # Index size %
                },
                "operations": {
                    "rate_levels": (1000, 5000),  # Operations per second
                    "queue_levels": (10, 50),  # Queued operations
                },
            },
            connection_parameters=[
                "hostname",
                "port",
                "database",
                "username",
                "password",
                "replica_set",
            ],
            performance_parameters=["cache_size", "connections", "oplog_size"],
        ),
        "mssql": DatabaseProfile(
            db_type="mssql",
            description="Microsoft SQL Server monitoring",
            common_metrics=[
                "connections",
                "databases",
                "locks",
                "memory",
                "transactions",
                "backup",
            ],
            default_parameters={
                "connections": {
                    "levels": (80.0, 90.0),  # % of max connections
                    "user_connections": (80.0, 90.0),
                },
                "databases": {
                    "size_levels": (80.0, 90.0),  # % used
                    "log_size_levels": (70.0, 85.0),  # Log file % used
                    "auto_grow": True,  # Check auto-growth events
                },
                "locks": {
                    "deadlock_levels": (1, 5),  # Deadlocks per second
                    "blocking_levels": (5, 20),  # Blocking processes
                    "timeout_levels": (1, 10),  # Lock timeouts per second
                },
                "memory": {
                    "target_levels": (80.0, 90.0),  # % of target memory
                    "buffer_hit_rate": (90.0, 95.0),  # Buffer cache hit rate
                    "page_life": (300, 180),  # Page life expectancy in seconds
                },
                "backup": {
                    "age_levels": (86400, 172800),  # Seconds since last backup
                    "failed_jobs": (0, 1),  # Failed backup jobs
                },
            },
            connection_parameters=[
                "hostname",
                "port",
                "database",
                "username",
                "password",
                "instance",
            ],
            performance_parameters=[
                "max_memory",
                "min_memory",
                "max_degree_parallelism",
                "cost_threshold",
            ],
        ),
        "redis": DatabaseProfile(
            db_type="redis",
            description="Redis monitoring",
            common_metrics=[
                "memory",
                "connections",
                "persistence",
                "replication",
                "keyspace",
            ],
            default_parameters={
                "memory": {
                    "levels": (80.0, 90.0),  # % of max memory
                    "fragmentation_levels": (1.5, 2.0),  # Memory fragmentation ratio
                    "evicted_keys": (100, 1000),  # Evicted keys per second
                },
                "connections": {
                    "levels": (80.0, 90.0),  # % of max clients
                    "rejected_levels": (1, 10),  # Rejected connections per second
                },
                "persistence": {
                    "rdb_age_levels": (3600, 7200),  # Seconds since last RDB save
                    "aof_size_levels": (
                        100 * 1024 * 1024,
                        500 * 1024 * 1024,
                    ),  # AOF file size
                },
                "replication": {
                    "lag_levels": (10, 30),  # Replication lag in seconds
                    "disconnected_slaves": (0, 1),  # Number of disconnected slaves
                },
            },
            connection_parameters=["hostname", "port", "password", "database"],
            performance_parameters=["maxmemory", "maxclients", "timeout"],
        ),
    }

    @property
    def name(self) -> str:
        """Unique name for this handler."""
        return "database"

    @property
    def service_patterns(self) -> List[str]:
        """Regex patterns that match database services."""
        return [
            r".*oracle.*",
            r".*mysql.*",
            r".*mariadb.*",
            r".*postgres.*",
            r".*postgresql.*",
            r".*mongo.*",
            r".*mssql.*",
            r".*sqlserver.*",
            r".*redis.*",
            r".*db2.*",
            r".*database.*",
            r".*tablespace.*",
            r".*connection.*pool.*",
            r".*replication.*",
            r".*backup.*job.*",
        ]

    @property
    def supported_rulesets(self) -> List[str]:
        """Rulesets this handler supports."""
        return [
            "checkgroup_parameters:oracle_tablespaces",
            "checkgroup_parameters:oracle_instance",
            "checkgroup_parameters:oracle_sessions",
            "checkgroup_parameters:oracle_locks",
            "checkgroup_parameters:mysql_connections",
            "checkgroup_parameters:mysql_innodb",
            "checkgroup_parameters:mysql_replication",
            "checkgroup_parameters:postgres_sessions",
            "checkgroup_parameters:postgres_locks",
            "checkgroup_parameters:postgres_bgwriter",
            "checkgroup_parameters:mongodb_collections",
            "checkgroup_parameters:mongodb_replication",
            "checkgroup_parameters:mssql_counters",
            "checkgroup_parameters:mssql_databases",
            "checkgroup_parameters:redis_info",
        ]

    def get_default_parameters(
        self, service_name: str, context: Optional[Dict[str, Any]] = None
    ) -> HandlerResult:
        """
        Get database-specific default parameters.

        Args:
            service_name: Name of the database service
            context: Optional context (database type, metric type, etc.)

        Returns:
            HandlerResult with database-specific defaults
        """
        # Determine database type and metric
        db_type, metric_type = self._detect_database_and_metric(service_name, context)
        profile = self.DATABASE_PROFILES.get(db_type)

        if not profile:
            # Generic database defaults
            parameters = {
                "levels": (80.0, 90.0),
                "connection_timeout": 30,
                "query_timeout": 60,
                "retry_count": 3,
                "perfdata": True,
            }
            messages = [
                self._create_validation_message(
                    ValidationSeverity.WARNING,
                    f"Unknown database type '{db_type}', using generic defaults",
                )
            ]
        else:
            # Get metric-specific defaults
            if metric_type and metric_type in profile.default_parameters:
                parameters = profile.default_parameters[metric_type].copy()
            else:
                # Use general database defaults
                parameters = {
                    "levels": (80.0, 90.0),
                    "connection_timeout": 30,
                    "query_timeout": 60,
                    "retry_count": 3,
                    "perfdata": True,
                }

                # Add database-specific connection parameters
                if profile.connection_parameters:
                    parameters["connection_params"] = {
                        param: None
                        for param in profile.connection_parameters[
                            :3
                        ]  # First 3 most important
                    }

            # Apply context-based adjustments
            if context:
                # Production environment gets more conservative settings
                if context.get("environment") == "production":
                    if "levels" in parameters and isinstance(
                        parameters["levels"], tuple
                    ):
                        warn, crit = parameters["levels"]
                        parameters["levels"] = (warn - 5, crit - 5)  # Lower thresholds

                    if "connection_timeout" in parameters:
                        parameters["connection_timeout"] = min(
                            parameters["connection_timeout"], 20
                        )

                # High-traffic environments
                if context.get("traffic_level") == "high":
                    if "absolute_levels" in parameters:
                        warn, crit = parameters["absolute_levels"]
                        parameters["absolute_levels"] = (warn * 2, crit * 2)

            messages = [
                self._create_validation_message(
                    ValidationSeverity.INFO, f"Using {profile.description} profile"
                ),
                self._create_validation_message(
                    ValidationSeverity.INFO, f"Metric type: {metric_type or 'general'}"
                ),
            ]

        return HandlerResult(
            success=True, parameters=parameters, validation_messages=messages
        )

    def validate_parameters(
        self,
        parameters: Dict[str, Any],
        service_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> HandlerResult:
        """
        Validate database monitoring parameters.

        Args:
            parameters: Parameters to validate
            service_name: Name of the database service
            context: Optional context information

        Returns:
            HandlerResult with validation results
        """
        messages = []
        normalized_params = parameters.copy()

        # Determine database type for context-aware validation
        db_type, metric_type = self._detect_database_and_metric(service_name, context)
        profile = self.DATABASE_PROFILES.get(db_type)

        # Validate common database parameters

        # Validate percentage-based levels
        if "levels" in parameters:
            levels_messages = self._validate_threshold_tuple(
                parameters["levels"], "levels", numeric_type=float
            )
            messages.extend(levels_messages)

            # Check percentage values
            if not levels_messages:
                warn, crit = parameters["levels"]
                if 0 <= warn <= 100 and 0 <= crit <= 100:
                    # Likely percentage thresholds
                    if warn >= crit:
                        messages.append(
                            self._create_validation_message(
                                ValidationSeverity.ERROR,
                                "Warning threshold must be less than critical threshold",
                                "levels",
                            )
                        )

                normalized_params["levels"] = (float(warn), float(crit))

        # Validate absolute levels (for connection counts, etc.)
        if "absolute_levels" in parameters:
            abs_messages = self._validate_threshold_tuple(
                parameters["absolute_levels"], "absolute_levels", numeric_type=int
            )
            messages.extend(abs_messages)

        # Validate connection parameters
        if "connection_timeout" in parameters:
            timeout_messages = self._validate_positive_number(
                parameters["connection_timeout"], "connection_timeout", int
            )
            messages.extend(timeout_messages)

            try:
                timeout = int(parameters["connection_timeout"])
                if timeout < 5:
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            "Connection timeout less than 5 seconds may be too short for database connections",
                            "connection_timeout",
                        )
                    )
                elif timeout > 300:
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            "Connection timeout longer than 5 minutes may cause monitoring delays",
                            "connection_timeout",
                        )
                    )
            except (TypeError, ValueError):
                pass

        # Database-specific validation
        if profile:
            if db_type == "oracle":
                oracle_messages = self._validate_oracle_parameters(
                    parameters, metric_type
                )
                messages.extend(oracle_messages)
            elif db_type == "mysql":
                mysql_messages = self._validate_mysql_parameters(
                    parameters, metric_type
                )
                messages.extend(mysql_messages)
            elif db_type == "postgresql":
                postgres_messages = self._validate_postgresql_parameters(
                    parameters, metric_type
                )
                messages.extend(postgres_messages)
            elif db_type == "mongodb":
                mongo_messages = self._validate_mongodb_parameters(
                    parameters, metric_type
                )
                messages.extend(mongo_messages)
            elif db_type == "mssql":
                mssql_messages = self._validate_mssql_parameters(
                    parameters, metric_type
                )
                messages.extend(mssql_messages)

        # Validate connection parameter structure
        if "connection_params" in parameters:
            conn_messages = self._validate_connection_params(
                parameters["connection_params"],
                profile.connection_parameters if profile else [],
            )
            messages.extend(conn_messages)

        return HandlerResult(
            success=len([m for m in messages if m.severity == ValidationSeverity.ERROR])
            == 0,
            parameters=parameters,
            normalized_parameters=normalized_params,
            validation_messages=messages,
        )

    def get_parameter_info(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """Get information about database parameters."""
        parameter_info = {
            "levels": {
                "description": "Percentage-based threshold levels",
                "type": "tuple",
                "elements": ["float", "float"],
                "example": "(80.0, 90.0)",
                "help": "Warning and critical thresholds as percentages",
            },
            "absolute_levels": {
                "description": "Absolute threshold levels",
                "type": "tuple",
                "elements": ["integer", "integer"],
                "example": "(500, 600)",
                "help": "Warning and critical thresholds as absolute values",
            },
            "connection_timeout": {
                "description": "Database connection timeout in seconds",
                "type": "integer",
                "default": 30,
                "min_value": 1,
                "max_value": 300,
                "help": "Maximum time to wait for database connection",
            },
            "query_timeout": {
                "description": "Database query timeout in seconds",
                "type": "integer",
                "default": 60,
                "min_value": 1,
                "max_value": 3600,
                "help": "Maximum time to wait for query execution",
            },
            "retry_count": {
                "description": "Number of retries on connection failure",
                "type": "integer",
                "default": 3,
                "min_value": 0,
                "max_value": 10,
                "help": "Number of times to retry failed database connections",
            },
            "connection_params": {
                "description": "Database connection parameters",
                "type": "dict",
                "help": "Dictionary containing hostname, port, database, username, etc.",
            },
            "perfdata": {
                "description": "Whether to collect performance data",
                "type": "boolean",
                "default": True,
                "help": "Enable collection of database performance metrics",
            },
            # Oracle-specific
            "magic_normsize": {
                "description": "Oracle tablespace normalization size in GB",
                "type": "integer",
                "default": 100,
                "help": "Used for Oracle tablespace percentage calculations",
            },
            "magic": {
                "description": "Oracle tablespace magic factor",
                "type": "float",
                "default": 0.9,
                "help": "Factor for Oracle tablespace threshold calculations",
            },
            # MySQL-specific
            "buffer_pool_hit_rate": {
                "description": "InnoDB buffer pool hit rate thresholds",
                "type": "tuple",
                "elements": ["float", "float"],
                "example": "(90.0, 95.0)",
                "help": "Warning and critical thresholds for buffer pool hit rate",
            },
            # PostgreSQL-specific
            "checkpoint_levels": {
                "description": "Background writer checkpoint thresholds",
                "type": "tuple",
                "elements": ["integer", "integer"],
                "example": "(300, 600)",
                "help": "Warning and critical levels for checkpoints per hour",
            },
            # MongoDB-specific
            "replica_set": {
                "description": "MongoDB replica set name",
                "type": "string",
                "help": "Name of the MongoDB replica set",
            },
        }

        return parameter_info.get(parameter_name)

    def suggest_parameters(
        self,
        service_name: str,
        current_parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Suggest database parameter optimizations."""
        suggestions = []

        current = current_parameters or {}
        db_type, metric_type = self._detect_database_and_metric(service_name, context)
        profile = self.DATABASE_PROFILES.get(db_type)

        if not profile:
            return suggestions

        # Suggest database-specific optimizations
        if metric_type and metric_type in profile.default_parameters:
            recommended = profile.default_parameters[metric_type]

            for param, default_value in recommended.items():
                if param not in current:
                    suggestions.append(
                        {
                            "parameter": param,
                            "current_value": None,
                            "suggested_value": default_value,
                            "reason": f"Recommended {param} setting for {profile.description} {metric_type}",
                            "impact": f"Optimized monitoring for {db_type} {metric_type}",
                        }
                    )

        # Database-specific suggestions
        if db_type == "oracle" and "tablespace" in service_name.lower():
            if "magic_normsize" not in current:
                suggestions.append(
                    {
                        "parameter": "magic_normsize",
                        "current_value": None,
                        "suggested_value": 100,
                        "reason": "Enable dynamic threshold calculation for Oracle tablespaces",
                        "impact": "More accurate alerting based on tablespace size",
                    }
                )

        elif db_type == "mysql" and "innodb" in service_name.lower():
            if "buffer_pool_hit_rate" not in current:
                suggestions.append(
                    {
                        "parameter": "buffer_pool_hit_rate",
                        "current_value": None,
                        "suggested_value": (90.0, 95.0),
                        "reason": "Monitor InnoDB buffer pool efficiency",
                        "impact": "Detect memory performance issues",
                    }
                )

        # Suggest connection monitoring for all databases
        if "connection" in service_name.lower() and "retry_count" not in current:
            suggestions.append(
                {
                    "parameter": "retry_count",
                    "current_value": None,
                    "suggested_value": 3,
                    "reason": "Add retry logic for database connection checks",
                    "impact": "Reduce false alerts from transient connection issues",
                }
            )

        return suggestions

    def _detect_database_and_metric(
        self, service_name: str, context: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """Detect database type and metric type from service name and context."""
        service_lower = service_name.lower()

        # Determine database type
        db_type = "unknown"
        if "oracle" in service_lower:
            db_type = "oracle"
        elif any(db in service_lower for db in ["mysql", "mariadb"]):
            db_type = "mysql"
        elif any(db in service_lower for db in ["postgres", "postgresql"]):
            db_type = "postgresql"
        elif "mongo" in service_lower:
            db_type = "mongodb"
        elif any(db in service_lower for db in ["mssql", "sqlserver"]):
            db_type = "mssql"
        elif "redis" in service_lower:
            db_type = "redis"

        # Determine metric type
        metric_type = None
        if "tablespace" in service_lower:
            metric_type = "tablespaces"
        elif "connection" in service_lower or "session" in service_lower:
            metric_type = "connections" if db_type != "oracle" else "sessions"
        elif "archive" in service_lower and "log" in service_lower:
            metric_type = "archive_logs"
        elif "redo" in service_lower and "log" in service_lower:
            metric_type = "redo_logs"
        elif "sga" in service_lower:
            metric_type = "sga"
        elif "pga" in service_lower:
            metric_type = "pga"
        elif "lock" in service_lower:
            metric_type = "locks"
        elif "replication" in service_lower or "replica" in service_lower:
            metric_type = "replication"
        elif "innodb" in service_lower:
            metric_type = "innodb"
        elif "bgwriter" in service_lower:
            metric_type = "bgwriter"
        elif "memory" in service_lower:
            metric_type = "memory"
        elif "backup" in service_lower:
            metric_type = "backup"

        # Use context if available
        if context:
            if context.get("database_type"):
                db_type = context["database_type"]
            if context.get("metric_type"):
                metric_type = context["metric_type"]

        return db_type, metric_type

    def _validate_oracle_parameters(
        self, parameters: Dict[str, Any], metric_type: Optional[str]
    ) -> List:
        """Validate Oracle-specific parameters."""
        messages = []

        if metric_type == "tablespaces":
            # Validate Oracle tablespace-specific parameters
            if "magic_normsize" in parameters:
                magic_messages = self._validate_positive_number(
                    parameters["magic_normsize"], "magic_normsize", int
                )
                messages.extend(magic_messages)

            if "magic" in parameters:
                try:
                    magic_val = float(parameters["magic"])
                    if not 0 < magic_val <= 1:
                        messages.append(
                            self._create_validation_message(
                                ValidationSeverity.ERROR,
                                "Oracle magic factor must be between 0 and 1",
                                "magic",
                            )
                        )
                except (TypeError, ValueError):
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.ERROR,
                            "Oracle magic factor must be a number",
                            "magic",
                        )
                    )

        return messages

    def _validate_mysql_parameters(
        self, parameters: Dict[str, Any], metric_type: Optional[str]
    ) -> List:
        """Validate MySQL-specific parameters."""
        messages = []

        if metric_type == "innodb":
            # Validate InnoDB-specific parameters
            if "buffer_pool_hit_rate" in parameters:
                hit_rate_messages = self._validate_threshold_tuple(
                    parameters["buffer_pool_hit_rate"], "buffer_pool_hit_rate"
                )
                messages.extend(hit_rate_messages)

                if not hit_rate_messages:
                    warn, crit = parameters["buffer_pool_hit_rate"]
                    if warn > 100 or crit > 100:
                        messages.append(
                            self._create_validation_message(
                                ValidationSeverity.ERROR,
                                "Buffer pool hit rate cannot exceed 100%",
                                "buffer_pool_hit_rate",
                            )
                        )

        elif metric_type == "replication":
            # Validate MySQL replication parameters
            if "lag_levels" in parameters:
                lag_messages = self._validate_threshold_tuple(
                    parameters["lag_levels"], "lag_levels", numeric_type=int
                )
                messages.extend(lag_messages)

        return messages

    def _validate_postgresql_parameters(
        self, parameters: Dict[str, Any], metric_type: Optional[str]
    ) -> List:
        """Validate PostgreSQL-specific parameters."""
        messages = []

        if metric_type == "bgwriter":
            # Validate background writer parameters
            if "checkpoint_levels" in parameters:
                checkpoint_messages = self._validate_threshold_tuple(
                    parameters["checkpoint_levels"],
                    "checkpoint_levels",
                    numeric_type=int,
                )
                messages.extend(checkpoint_messages)

        elif metric_type == "vacuum":
            # Validate vacuum-related parameters
            if "age_levels" in parameters:
                age_messages = self._validate_threshold_tuple(
                    parameters["age_levels"], "age_levels", numeric_type=int
                )
                messages.extend(age_messages)

        return messages

    def _validate_mongodb_parameters(
        self, parameters: Dict[str, Any], metric_type: Optional[str]
    ) -> List:
        """Validate MongoDB-specific parameters."""
        messages = []

        if "replica_set" in parameters:
            replica_set = parameters["replica_set"]
            if not isinstance(replica_set, str) or not replica_set.strip():
                messages.append(
                    self._create_validation_message(
                        ValidationSeverity.ERROR,
                        "replica_set must be a non-empty string",
                        "replica_set",
                    )
                )

        return messages

    def _validate_mssql_parameters(
        self, parameters: Dict[str, Any], metric_type: Optional[str]
    ) -> List:
        """Validate MSSQL-specific parameters."""
        messages = []

        if metric_type == "memory":
            # Validate SQL Server memory parameters
            if "page_life" in parameters:
                page_life_messages = self._validate_threshold_tuple(
                    parameters["page_life"], "page_life", numeric_type=int
                )
                messages.extend(page_life_messages)

                # Note: For page life expectancy, higher is better, so thresholds are reversed
                if not page_life_messages:
                    warn, crit = parameters["page_life"]
                    if warn <= crit:
                        messages.append(
                            self._create_validation_message(
                                ValidationSeverity.ERROR,
                                "For page life expectancy, warning threshold should be higher than critical",
                                "page_life",
                                "Page life expectancy: higher values are better",
                            )
                        )

        return messages

    def _validate_connection_params(
        self, conn_params: Any, expected_params: List[str]
    ) -> List:
        """Validate database connection parameters structure."""
        messages = []

        if not isinstance(conn_params, dict):
            messages.append(
                self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "connection_params must be a dictionary",
                    "connection_params",
                )
            )
            return messages

        # Check for required connection parameters
        required_params = expected_params if expected_params else ["hostname"]
        for param in required_params:
            if param not in conn_params or not conn_params[param]:
                messages.append(
                    self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"Required connection parameter '{param}' is missing or empty",
                        "connection_params",
                    )
                )

        # Validate parameter values
        for param, value in conn_params.items():
            if param == "port":
                try:
                    port = int(value)
                    if not 1 <= port <= 65535:
                        messages.append(
                            self._create_validation_message(
                                ValidationSeverity.ERROR,
                                f"Port must be between 1 and 65535, got {port}",
                                "connection_params",
                            )
                        )
                except (TypeError, ValueError):
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.ERROR,
                            "Port must be an integer",
                            "connection_params",
                        )
                    )

            elif param == "hostname":
                if not isinstance(value, str) or not value.strip():
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.ERROR,
                            "Hostname must be a non-empty string",
                            "connection_params",
                        )
                    )

        # Suggest additional parameters if available
        if expected_params:
            missing_optional = set(expected_params) - set(conn_params.keys())
            if missing_optional:
                messages.append(
                    self._create_validation_message(
                        ValidationSeverity.INFO,
                        f"Optional connection parameters available: {', '.join(missing_optional)}",
                        "connection_params",
                    )
                )

        return messages
