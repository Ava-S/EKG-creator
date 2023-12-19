from typing import Optional, List, Union

from ..data_managers.semantic_header import ConstructedNodes, ConstructedRelation, Relationship, SemanticHeader, \
    NodeConstructor
from ..database_managers.db_connection import DatabaseConnection
from ..utilities.performance_handling import Performance
from ..cypher_queries.semantic_header_ql import SemanticHeaderQueryLibrary as sh_ql


class EKGUsingSemanticHeaderBuilder:
    def __init__(self):
        self.connection = DatabaseConnection()
        self.semantic_header = SemanticHeader()

    def create_nodes_by_records(self, node_types: Optional[List[str]]) -> None:
        for node_constructor in self.semantic_header.get_node_by_record_constructors(node_types):
            self._create_node_by_record(node_constructor=node_constructor)

    @Performance.track("node_constructor")
    def _create_node_by_record(self, node_constructor: NodeConstructor):
        num_ids = self.connection.exec_query(sh_ql.get_number_of_ids_query,
                                             **{
                                                 "node_constructor": node_constructor,
                                                 "use_record": True
                                             })
        merge_first = num_ids[0]['num_ids'] < 1000 \
                        and "Event" not in node_constructor.get_labels() \
                        and "EntityAttribute" not in node_constructor.get_labels()

        self.connection.exec_query(sh_ql.get_create_node_by_record_constructor_query,
                                   **{
                                       "node_constructor": node_constructor,
                                       "merge": merge_first
                                   })

        self.connection.exec_query(sh_ql.get_reset_created_record_query)

        if merge_first:
            print(
                f"Node ({node_constructor.get_pattern(with_properties=False)})"
                f"using ({node_constructor.get_prevalent_record_pattern()}) merged")
        else:
            print(f"Node ({node_constructor.get_pattern(with_properties=False)}) "
                  f"using ({node_constructor.get_prevalent_record_pattern()}) "
                  f"created")
            if not ("Event" in node_constructor.get_labels() or "EntityAttribute" in node_constructor.get_labels()):
                self.connection.exec_query(sh_ql.get_merge_nodes_with_same_id_query,
                                           **{
                                               "node_constructor": node_constructor
                                           }
                                           )

                self.connection.exec_query(sh_ql.get_reset_merged_in_nodes_query,
                                           **{
                                               "node_constructor": node_constructor}
                                           )

    def create_nodes_by_relations(self, node_types: Optional[List[str]]) -> None:
        for node_constructors in self.semantic_header.get_nodes_constructed_by_relations(node_types).values():
            for node_constructor in node_constructors:
                self._create_node_by_relation(node_constructor=node_constructor)

    @Performance.track("node_constructor")
    def _create_node_by_relation(self, node_constructor: NodeConstructor):
        pass

    def create_relations_using_records(self, relation_types: Optional[List[str]]) -> None:
        # find events that are related to different entities of which one event also has a reference to the other entity
        # create a relation between these two entities
        relation: ConstructedRelation
        for relation_constructor in self.semantic_header.get_relations_constructed_by_record(relation_types):
            self._create_relations_using_record(relation_constructor=relation_constructor)

    @Performance.track("relation_constructor")
    def _create_relations_using_record(self, relation_constructor):
        self.connection.exec_query(sh_ql.get_create_relation_using_record_query,
                                   **{
                                       "relation_constructor": relation_constructor
                                   })
        self.connection.exec_query(sh_ql.get_reset_created_record_query)
        self._create_corr_from_parents(relation_constructor=relation_constructor)

    def create_relations_using_relations(self, relation_types: Optional[List[str]]) -> None:
        relation: ConstructedRelation
        for relation_constructor in self.semantic_header.get_relations_constructed_by_relations(relation_types):
            self._create_relations_using_relation(relation_constructor=relation_constructor)

    @Performance.track("relation_constructor")
    def _create_relations_using_relation(self, relation_constructor):
        self.connection.exec_query(sh_ql.get_create_relation_by_relations_query,
                                   **{
                                       "relation_constructor": relation_constructor
                                   })
        self._create_corr_from_parents(relation_constructor=relation_constructor)

    def _create_corr_from_parents(self, relation_constructor):
        if relation_constructor.infer_corr_from_reified_parents:
            for use_from in [True, False]:
                self.connection.exec_query(sh_ql.get_infer_corr_from_parent_query,
                                           **{
                                               "relation_constructor": relation_constructor,
                                               "use_from": use_from
                                           })

    def create_df_edges(self, entity_types: List[str], event_label: str) -> None:
        entity: ConstructedNodes

        if entity_types is None:
            entity_types = [entity.type for entity in self.semantic_header.nodes] \
                           + [relation.type for relation in self.semantic_header.relations if relation.model_as_node]

        for entity in self.semantic_header.nodes:
            if entity.infer_df and entity.type in entity_types:
                self._create_df_edges_for_entity(entity=entity, event_label=event_label)

        for relation in self.semantic_header.relations:
            if relation.model_as_node and relation.infer_df and relation.type in entity_types:
                self._create_df_edges_for_entity(entity=relation, event_label=event_label)

    @Performance.track("entity")
    def _create_df_edges_for_entity(self, entity: Union[ConstructedNodes, ConstructedRelation], event_label):
        self.connection.exec_query(sh_ql.get_create_directly_follows_query,
                                   **{
                                       "entity": entity,
                                       "event_label": event_label
                                   })

    def merge_duplicate_df(self):
        node: ConstructedNodes
        for node in self.semantic_header.nodes:
            if node.merge_duplicate_df:
                self._merge_duplicate_df_for_node(node=node)

    @Performance.track("node")
    def _merge_duplicate_df_for_node(self, node: ConstructedNodes):
        self.connection.exec_query(sh_ql.get_merge_duplicate_df_entity_query, **{"node": node})

    def create_static_nodes_and_relations(self):
        print("No implementation yet")
        pass